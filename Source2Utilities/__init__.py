import bpy
import bmesh
from mathutils import Vector
from bpy.props import (
    StringProperty,
    BoolProperty,
    EnumProperty,
)
from bpy.types import Panel, Operator
from bpy.app.handlers import persistent

# Global variable for shading settings preservation
shading_preserve = ['SOLID', 'MATCAP', 'MATERIAL', False]

###################################
# COMMON MODULE (Helper functions)
###################################
def get_object_dimensions(obj):
    """
    Retrieve an object's bounding-box dimensions in centimeters.
    (For example, an object 2 m wide will yield 200.)
    """
    if not obj:
        return (0, 0, 0)
    scale = bpy.context.scene.unit_settings.scale_length
    coords = [obj.matrix_world @ vert.co for vert in obj.data.vertices]
    xs = [v.x for v in coords]
    ys = [v.y for v in coords]
    zs = [v.z for v in coords]
    return (int(round((max(xs) - min(xs)) * scale * 100)),
            int(round((max(ys) - min(ys)) * scale * 100)),
            int(round((max(zs) - min(zs)) * scale * 100)))
def format_dimensions(dimensions, size_format):
    """Format dimensions as requested (X, Y, Z, XY, XZ, or XYZ)."""
    x, y, z = dimensions
    if size_format == 'X':
        return str(x)
    elif size_format == 'Y':
        return str(y)
    elif size_format == 'Z':
        return str(z)
    elif size_format == 'XY':
        return f"{x}_{y}"
    elif size_format == 'XZ':
        return f"{x}_{z}"
    elif size_format == 'XYZ':
        return f"{x}_{y}_{z}"
    return ""

def increment_suffix(suffix):
    """Increment an alphabetic suffix (e.g., 'a' becomes 'b'; 'z' becomes 'aa')."""
    if not suffix or not suffix.isalpha():
        return 'a'
    last_char = suffix[-1]
    rest = suffix[:-1]
    if last_char == 'z':
        return (increment_suffix(rest) + 'a') if rest else 'aa'
    return rest + chr(ord(last_char) + 1)

def ensure_attribute_exists(obj, attr_name, domain='CORNER', data_type='BYTE_COLOR', dimensions=3):
    """Ensure the specified attribute exists on mesh data; create if missing."""
    if not obj or obj.type != 'MESH':
        return None
    if attr_name in obj.data.attributes:
        return obj.data.attributes[attr_name]
    return obj.data.attributes.new(name=attr_name, type=data_type, domain=domain)

def report_error(self, message):
    self.report({'ERROR'}, message)
    return {'CANCELLED'}

def report_info(self, message):
    self.report({'INFO'}, message)
    return {'FINISHED'}

###################################
# NAMING MODULE
###################################
class OBJECT_OT_apply_naming_convention(Operator):
    """Apply the Source 2 naming convention to selected objects."""
    bl_idname = "object.apply_naming_convention"
    bl_label = "Apply Naming Convention"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        selected_objects = context.selected_objects
        if not selected_objects:
            return report_error(self, "No objects selected")
        if not scene.s2_suffix.isalpha():
            return report_error(self, "Suffix must be alphabetic")

        used_names = set()
        current_suffix = scene.s2_suffix

        for obj in selected_objects:
            if obj.type != 'MESH':
                continue
            name_parts = [scene.s2_prefix, scene.s2_name]
            if scene.s2_add_sizes:
                dimensions = get_object_dimensions(obj)
                size_str = format_dimensions(dimensions, scene.s2_size_format)
                if size_str:
                    name_parts.append(size_str)
            name_parts.append(current_suffix)
            new_name = "_".join([part for part in name_parts if part])
            while new_name in used_names:
                current_suffix = increment_suffix(current_suffix)
                name_parts[-1] = current_suffix
                new_name = "_".join([part for part in name_parts if part])
            obj.name = new_name
            used_names.add(new_name)
            current_suffix = increment_suffix(current_suffix)
        return report_info(self, f"Applied naming convention to {len(selected_objects)} objects")

def naming_register():
    bpy.utils.register_class(OBJECT_OT_apply_naming_convention)

def naming_unregister():
    try:
        bpy.utils.unregister_class(OBJECT_OT_apply_naming_convention)
    except RuntimeError:
        pass

###################################
# UV ATTRIBUTES MODULE
###################################
class OBJECT_OT_rename_uv_maps(Operator):
    """Rename UV maps to match Source 2 format (map, map1, map2, etc.)."""
    bl_idname = "object.rename_uv_maps"
    bl_label = "Rename UV Maps"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return report_error(self, "No mesh object selected")
        uv_layers = obj.data.uv_layers
        if not uv_layers:
            return report_error(self, "No UV maps found on the selected object")
        for i, uv_layer in enumerate(uv_layers):
            uv_layer.name = "map" if i == 0 else f"map{i}"
        return report_info(self, f"Renamed {len(uv_layers)} UV maps to Source 2 format")

class OBJECT_OT_convert_color_attributes(Operator):
    """
    Convert color attributes to Source 2 format.
    (This converts attributes to use CORNER domain and BYTE_COLOR data type.)
    """
    bl_idname = "object.convert_color_attributes"
    bl_label = "Convert Color Attributes"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return report_error(self, "No mesh object selected")
        target_attributes = ["VertexPaintTintColor", "VertexPaintBlendParams"]
        converted_count = 0
        created_count = 0

        for attr_name in target_attributes:
            if attr_name in obj.data.attributes:
                attr = obj.data.attributes[attr_name]
                if attr.domain == 'CORNER' and attr.data_type == 'BYTE_COLOR':
                    continue  # already correct
                temp_data = []
                if attr.domain == 'POINT':
                    for v in obj.data.vertices:
                        faces = [f for f in obj.data.polygons if v.index in f.vertices]
                        for _ in range(len(faces)):
                            temp_data.append((1.0, 1.0, 1.0, 1.0))
                else:
                    for i in range(len(attr.data)):
                        temp_data.append(getattr(attr.data[i], 'color', (1.0, 1.0, 1.0, 1.0)))
                obj.data.attributes.remove(attr)
                new_attr = ensure_attribute_exists(obj, attr_name, 'CORNER', 'BYTE_COLOR', 3)
                for i, loop in enumerate(obj.data.loops):
                    if i < len(temp_data):
                        new_attr.data[i].color = temp_data[i][:3] + (1.0,)
                converted_count += 1
            else:
                new_attr = ensure_attribute_exists(obj, attr_name, 'CORNER', 'BYTE_COLOR', 3)
                if attr_name == "VertexPaintBlendParams":
                    for i in range(len(obj.data.loops)):
                        new_attr.data[i].color = (0.0, 0.0, 0.0, 1.0)
                created_count += 1
        msg = f"Processed color attributes: {converted_count} converted, {created_count} created"
        return report_info(self, msg)

def uv_attributes_register():
    bpy.utils.register_class(OBJECT_OT_rename_uv_maps)
    bpy.utils.register_class(OBJECT_OT_convert_color_attributes)

def uv_attributes_unregister():
    for cls in (OBJECT_OT_convert_color_attributes, OBJECT_OT_rename_uv_maps):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass

###################################
# AO BAKING MODULE
###################################
class OBJECT_OT_bake_ao_to_selected_attribute(Operator):
    """
    Bake ambient occlusion into the chosen color attribute (Color Tint or Vertex Blend).
    """
    bl_idname = "object.bake_ao_to_selected_attribute"
    bl_label = "Bake AO"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return report_error(self, "No mesh object selected")
        target_attr = context.scene.s2_ao_attribute
        attr = ensure_attribute_exists(obj, target_attr, 'CORNER', 'BYTE_COLOR', 3)
        if not attr:
            return report_error(self, f"Failed to create '{target_attr}' attribute")
        original_mode = obj.mode
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
            temp_image = bpy.data.images.new(name="temp_ao_bake", width=1024, height=1024)
            temp_mat = bpy.data.materials.new(name="temp_ao_bake_material")
            temp_mat.use_nodes = True
            if not obj.material_slots:
                obj.data.materials.append(temp_mat)
            else:
                obj.material_slots[0].material = temp_mat
            nodes = temp_mat.node_tree.nodes
            links = temp_mat.node_tree.links
            nodes.clear()
            texture_node = nodes.new('ShaderNodeTexImage')
            texture_node.image = temp_image
            nodes.active = texture_node
            output_node = nodes.new('ShaderNodeOutputMaterial')
            diffuse_node = nodes.new('ShaderNodeBsdfDiffuse')
            links.new(diffuse_node.outputs['BSDF'], output_node.inputs['Surface'])
            bpy.ops.object.bake(type='AO', save_mode='INTERNAL')
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            bm.faces.ensure_lookup_table()
            if not obj.data.uv_layers:
                bpy.ops.mesh.uv_texture_add()
            uv_layer = bm.loops.layers.uv.active
            color_layer = bm.loops.layers.color.get(target_attr)
            if not color_layer:
                color_layer = bm.loops.layers.color.new(target_attr)
            for face in bm.faces:
                for loop in face.loops:
                    uv = loop[uv_layer].uv
                    x = int(uv.x * temp_image.size[0]) % temp_image.size[0]
                    y = int(uv.y * temp_image.size[1]) % temp_image.size[1]
                    pixel_index = (y * temp_image.size[0] + x) * 4
                    if pixel_index < len(temp_image.pixels):
                        r = temp_image.pixels[pixel_index]
                        g = temp_image.pixels[pixel_index+1]
                        b = temp_image.pixels[pixel_index+2]
                        loop[color_layer] = (r, g, b, 1.0)
            bm.to_mesh(obj.data)
            obj.data.update()
            bm.free()
            bpy.data.images.remove(temp_image)
            bpy.data.materials.remove(temp_mat)
            bpy.ops.object.mode_set(mode=original_mode)
            return report_info(self, f"Successfully baked AO to '{target_attr}'")
        except Exception as e:
            bpy.ops.object.mode_set(mode=original_mode)
            return report_error(self, f"Error during AO baking: {str(e)}")

def ao_baking_register():
    bpy.utils.register_class(OBJECT_OT_bake_ao_to_selected_attribute)

def ao_baking_unregister():
    try:
        bpy.utils.unregister_class(OBJECT_OT_bake_ao_to_selected_attribute)
    except RuntimeError:
        pass

###################################
# MAIN PANEL
###################################
class VIEW3D_PT_source2_utilities(Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Source 2'
    bl_label = "Source 2 Utilities"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # Object Naming Section
        box = layout.box()
        box.label(text="Object Naming", icon='SORTALPHA')
        row = box.row()
        row.prop(scene, "s2_prefix", text="Prefix")
        row = box.row()
        row.prop(scene, "s2_name", text="Name")
        row = box.row()
        row.prop(scene, "s2_suffix", text="Suffix")
        row = box.row()
        row.prop(scene, "s2_add_sizes", text="Include Sizes")
        if scene.s2_add_sizes:
            row = box.row()
            row.prop(scene, "s2_size_format", text="Size Format")
        row = box.row()
        row.operator("object.apply_naming_convention", text="Apply Naming")

        layout.separator()

        # UV Maps and Attributes Section
        box = layout.box()
        box.label(text="UV Maps & Attributes", icon='GROUP_UVS')
        row = box.row()
        row.operator("object.rename_uv_maps", text="Rename UV Maps")
        row = box.row()
        row.operator("object.convert_color_attributes", text="Convert Color Attributes")
        row = box.row()
        row.prop(scene, "s2_auto_apply_to_new", text="Auto Apply to New Objects")

        layout.separator()

        # AO Baking Section
        box = layout.box()
        box.label(text="Ambient Occlusion Baking", icon='SHADING_RENDERED')
        row = box.row()
        row.prop(scene, "s2_ao_attribute", text="Target")
        row = box.row()
        row.operator("object.bake_ao_to_selected_attribute", text="Bake AO to Attribute")

###################################
# PROPERTIES AND HANDLERS
###################################
def register_properties():
    bpy.types.Scene.s2_prefix = StringProperty(
        name="Name",
        description="Prefix for object naming",
        default="prop"
    )
    bpy.types.Scene.s2_name = StringProperty(
        name="Variation",
        description="Core name for the object",
        default="01"
    )
    bpy.types.Scene.s2_suffix = StringProperty(
        name="Suffix",
        description="Alphabetic suffix for the object",
        default="a"
    )
    bpy.types.Scene.s2_add_sizes = BoolProperty(
        name="Include Sizes",
        description="Include object dimensions in the name",
        default=False
    )
    bpy.types.Scene.s2_size_format = EnumProperty(
        name="Size Format",
        description="Dimensions to include in the name",
        items=[
            ('X', "Only X", "Include only X dimension"),
            ('Y', "Only Y", "Include only Y dimension"),
            ('Z', "Only Z", "Include only Z dimension"),
            ('XY', "XY", "Include X & Y dimensions"),
            ('XZ', "XZ", "Include X & Z dimensions"),
            ('XYZ', "XYZ", "Include X, Y & Z dimensions"),
        ],
        default='XYZ'
    )
    bpy.types.Scene.s2_auto_apply_to_new = BoolProperty(
        name="Auto Apply to New Objects",
        description="Automatically apply UV renaming and attribute conversion",
        default=False
    )
    bpy.types.Scene.s2_ao_attribute = EnumProperty(
        name="AO Attribute",
        items=[
            ("VertexPaintTintColor", "Color Tint", "Bake AO into the VertexPaintTintColor attribute"),
            ("VertexPaintBlendParams", "Vertex Blend", "Bake AO into the VertexPaintBlendParams attribute"),
        ],
        default="VertexPaintTintColor",
        description="Attribute to store baked Ambient Occlusion"
    )

@persistent
def on_object_add(depsgraph):
    scene = bpy.context.scene
    if not scene.s2_auto_apply_to_new:
        return
    obj = bpy.context.active_object
    if obj and obj.type == 'MESH':
        # Auto apply UV renaming and conversion on new objects
        rename_uv_maps(obj)
        OBJECT_OT_convert_color_attributes().execute(bpy.context)

def unregister_properties():
    for prop in ["s2_prefix", "s2_name", "s2_suffix", "s2_add_sizes", "s2_size_format", "s2_auto_apply_to_new", "s2_ao_attribute"]:
        try:
            delattr(bpy.types.Scene, prop)
        except Exception:
            pass

###################################
# REGISTER & UNREGISTER
###################################
def register():
    try:
        register_properties()
        bpy.utils.register_class(VIEW3D_PT_source2_utilities)
        common_register()
        naming_register()
        uv_attributes_register()
        ao_baking_register()
        if on_object_add not in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.append(on_object_add)
    except Exception as e:
        print(f"Error registering Source 2 Utilities: {e}")
        unregister()
        raise

def unregister():
    try:
        if on_object_add in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.remove(on_object_add)
    except Exception:
        pass
    for unregister_func in (ao_baking_unregister, uv_attributes_unregister, naming_unregister):
        try:
            unregister_func()
        except Exception:
            pass
    try:
        bpy.utils.unregister_class(VIEW3D_PT_source2_utilities)
    except Exception:
        pass
    unregister_properties()
    common_unregister()

if __name__ == "__main__":
    register()