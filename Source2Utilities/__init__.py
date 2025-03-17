import bpy
import bmesh
import random
import math
import statistics
from mathutils import Vector
from bpy.props import (
    StringProperty,
    BoolProperty,
    EnumProperty,
    IntProperty,
    FloatProperty,
)
from bpy.types import Panel, Operator
from bpy.app.handlers import persistent

bl_info = {
    'name': 'Source 2 Utilities',
    'author': 'Nucky3d',
    'version': (1, 0, 0),
    'blender': (3, 5, 0),
    'location': 'View3D > Source 2',
    'description': 'Utility tools for Source 2 workflows',
    'doc_url': '',
    'tracker_url': '',
    'category': 'Object'
}

# Track Blender version
version, _, _ = bpy.app.version

###################################
# HELPER: Build a proper override
###################################
def get_override(context, obj):
    """Return an override dictionary including area and region from a 3D View, if available."""
    override = context.copy()
    # Try to find a 3D View area
    for area in context.screen.areas:
        if area.type == "VIEW_3D":
            override["area"] = area
            # Look for a window region in that area.
            for region in area.regions:
                if region.type == "WINDOW":
                    override["region"] = region
                    break
            break
    override["object"] = obj
    override["active_object"] = obj
    override["selected_objects"] = [obj]
    override["selected_editable_objects"] = [obj]
    return override

###################################
# COMMON MODULE (Helper functions)
###################################
def get_object_dimensions(obj):
    """
    Retrieve an object's bounding-box dimensions in centimeters.
    (For example, an object 2 m wide will yield 200.)
    """
    if not obj or not hasattr(obj, 'data') or not hasattr(obj.data, 'vertices'):
        return (0, 0, 0)
    scale = bpy.context.scene.unit_settings.scale_length
    coords = [obj.matrix_world @ vert.co for vert in obj.data.vertices]
    if not coords:
        return (0, 0, 0)
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
# SXAO Utility Classes
###################################
class SXAO_utils:
    """Lightweight utility class for bounding box, etc., from sxao.py."""
    def __init__(self):
        pass

    def find_root_pivot(self, objs):
        xmin, xmax, ymin, ymax, zmin, zmax = self.get_object_bounding_box(objs)
        pivot = ((xmax + xmin)*0.5, (ymax + ymin)*0.5, zmin)
        return pivot

    def get_object_bounding_box(self, objs, local=False):
        bbx_x = []
        bbx_y = []
        bbx_z = []
        for obj in objs:
            if local:
                corners = [Vector(corner) for corner in obj.bound_box]
            else:
                corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
            for corner in corners:
                bbx_x.append(corner[0])
                bbx_y.append(corner[1])
                bbx_z.append(corner[2])
        xmin, xmax = min(bbx_x), max(bbx_x)
        ymin, ymax = min(bbx_y), max(bbx_y)
        zmin, zmax = min(bbx_z), max(bbx_z)
        return xmin, xmax, ymin, ymax, zmin, zmax

class SXAO_generate:
    """Main AO generation logic adapted from sxao.py."""
    def __init__(self):
        pass

    def ray_randomizer(self, count):
        hemisphere = [None] * count
        random.seed(42)
        for i in range(count):
            u1 = random.random()
            u2 = random.random()
            r = math.sqrt(u1)
            theta = 2*math.pi*u2
            x = r * math.cos(theta)
            y = r * math.sin(theta)
            z = math.sqrt(max(0, 1 - u1))

            ray = Vector((x, y, z))
            up_vector = Vector((0, 0, 1))
            dot_product = ray.dot(up_vector)

            hemisphere[i] = (ray, dot_product)
        sorted_hemisphere = sorted(hemisphere, key=lambda x: x[1], reverse=True)
        return sorted_hemisphere

    def vertex_data_dict(self, obj, dots=False):
        """
        Gather vertex data (local coords, local normal, world coords, world normal, min_dot).
        If dots=True, compute minimal dot with connected edges in local space (helps skip rays).
        """
        mesh = obj.data
        mat = obj.matrix_world
        vertex_dict = {}
        bm = None
        if dots:
            bm = bmesh.new()
            bm.from_mesh(mesh)
            bm.normal_update()
            bmesh.types.BMVertSeq.ensure_lookup_table(bm.verts)

        for v in range(len(mesh.vertices)):
            co_local = mesh.vertices[v].co
            no_local = mesh.vertices[v].normal
            co_world = mat @ co_local
            no_world = (mat @ (co_local + no_local)) - mat @ co_local
            no_world.normalize()

            min_dot = 0.0
            if dots and bm:
                if v < len(bm.verts):
                    bm_vert = bm.verts[v]
                    dot_list = []
                    for edge in bm_vert.link_edges:
                        other_co = edge.other_vert(bm_vert).co
                        direction = (other_co - bm_vert.co).normalized()
                        dot_list.append(no_local.normalized().dot(direction))
                    if dot_list:
                        min_dot = min(dot_list)
            vertex_dict[v] = [co_local, no_local, co_world, no_world, min_dot]

        if bm:
            bm.free()
        return vertex_dict

    def occlusion_list(self, obj, raycount=250, blend=0.5, dist=10.0, groundplane=False):
        """
        Compute an AO-like occlusion value for each loop using a simplified approach
        from sxao.py via random rays in local and global space.
        Return a list of RGBA colors for each loop (1 color per loop).
        """
        hemi_sphere = self.ray_randomizer(raycount)
        contribution = 1.0 / float(raycount)
        clamp_blend = max(min(blend, 1.0), 0.0)

        edg = bpy.context.evaluated_depsgraph_get()
        obj_eval = obj.evaluated_get(edg)

        forward = Vector((0, 0, 1))

        vert_dict = self.vertex_data_dict(obj, dots=True)
        if not vert_dict:
            return None

        vert_occ = {}
        for v_id in vert_dict.keys():
            vert_occ[v_id] = 1.0

        for v_id, data in vert_dict.items():
            bias = 0.001
            local_co, local_no, world_co, world_no, min_dot = data

            hit, loc, normal, idx = obj.ray_cast(local_co, local_no, distance=dist)
            if hit and normal.dot(local_no) > 0:
                hit_dist = (loc - local_co).length
                if hit_dist < 0.5:
                    bias += hit_dist

            first_hit_index = raycount
            for i, (_, dot_val) in enumerate(hemi_sphere):
                if dot_val < min_dot:
                    first_hit_index = i
                    break
            occ_value = 1.0
            occ_value -= contribution * (raycount - first_hit_index)

            valid_rays = [ray for ray, _ in hemi_sphere[:first_hit_index]]
            pass2_hits = [False] * len(valid_rays)

            if clamp_blend < 1.0:
                from_up = forward.rotation_difference(local_no)
                local_pos = local_co + (bias * local_no)
                for i, r_dir in enumerate(valid_rays):
                    hit_local = obj_eval.ray_cast(local_pos, from_up @ r_dir, distance=dist)[0]
                    if hit_local:
                        occ_value -= contribution
                    pass2_hits[i] = hit_local

            if clamp_blend > 0.0:
                from_up = forward.rotation_difference(world_no)
                world_pos = world_co + (bias * world_no)
                scn_occ_value = occ_value
                for i, r_dir in enumerate(valid_rays):
                    if not pass2_hits[i]:
                        scene_hit = bpy.context.scene.ray_cast(edg, world_pos, from_up @ r_dir, distance=dist)[0]
                        if scene_hit:
                            scn_occ_value -= contribution
                occ_value = (occ_value * (1.0 - clamp_blend)) + (scn_occ_value * clamp_blend)

            vert_occ[v_id] = max(0.0, min(occ_value, 1.0))

        loop_colors = [0.0, 0.0, 0.0, 1.0] * len(obj.data.loops)
        for poly in obj.data.polygons:
            for vert_idx, loop_idx in zip(poly.vertices, poly.loop_indices):
                val = vert_occ[vert_idx]
                loop_colors[loop_idx * 4 : loop_idx * 4 + 4] = [val, val, val, 1.0]
        return loop_colors

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

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return report_error(self, "No mesh object selected")
        if not obj.data.uv_layers:
            obj.data.uv_layers.new(name="map")
            return report_info(self, "Created new UV map named 'map'")
        uv_layers = obj.data.uv_layers
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

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'MESH'

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
                # Overwrite any existing data unconditionally.
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
# AO BAKING MODULE (Replaced with SXAO logic)
###################################
class OBJECT_OT_bake_ao_to_selected_attribute(Operator):
    """
    Use the SXAO logic from sxao.py to compute an AO-like occlusion
    for each vertex/loop. This replaces the old Blender bake approach.
    """
    bl_idname = "object.bake_ao_to_selected_attribute"
    bl_label = "Bake AO (SXAO)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return report_error(self, "No mesh object selected")

        scene = context.scene
        # Get AO settings from scene properties
        target_attr = scene.s2_ao_attribute
        ray_count = scene.s2_ao_ray_count
        local_global_mix = scene.s2_ao_global_local_mix
        ray_distance = scene.s2_ao_distance
        ground_plane = scene.s2_ao_ground_plane
        geonode_ao = scene.s2_ao_geonode_ao

        # Here you can conditionally choose between algorithms.
        # For now, if geonode_ao is True, you might call a different function.
        # We'll default to the SXAO algorithm for this example.
        # Overwrite any existing data in the color attribute:
        attr = ensure_attribute_exists(obj, target_attr, 'CORNER', 'BYTE_COLOR', 3)
        if not attr:
            return report_error(self, f"Failed to create '{target_attr}' attribute")

        generator = SXAO_generate()
        colors = generator.occlusion_list(
            obj,
            raycount=ray_count,
            blend=local_global_mix,
            dist=ray_distance,
            groundplane=ground_plane
        )
        if not colors:
            return report_error(self, "AO calculation returned no data")

        if len(colors) == 4 * len(obj.data.loops):
            # Overwrite the entire attribute data
            attr.data.foreach_set("color", colors)
        else:
            return report_error(self, "Loop color array size mismatch")

        # Set the active color attribute to the one we just baked
        obj.data.attributes.active_color = obj.data.attributes[target_attr]

        # Update the 3D View preview to show vertex colors with flat shading
        # This matches the behavior in sxao.py
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.shading.type = 'SOLID'
                area.spaces.active.shading.color_type = 'VERTEX'
                area.spaces.active.shading.light = 'FLAT'

        return report_info(self, f"Successfully baked SXAO to '{target_attr}'")

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
        box.label(text="Ambient Occlusion Baking (SXAO)", icon='SHADING_RENDERED')
        row = box.row()
        row.prop(scene, "s2_ao_attribute", text="Target")
        row = box.row()
        row.prop(scene, "s2_ao_ray_count", text="Ray Count")
        row = box.row()
        row.prop(scene, "s2_ao_distance", text="Ray Distance")
        row = box.row()
        row.prop(scene, "s2_ao_global_local_mix", text="Global Local Mix")
        row = box.row()
        row.prop(scene, "s2_ao_ground_plane", text="Ground Plane")
        row = box.row()
        row.prop(scene, "s2_ao_geonode_ao", text="Geonode AO")
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
    # New AO baking properties
    bpy.types.Scene.s2_ao_ray_count = IntProperty(
        name="Ray Count",
        description="Number of rays to use for AO calculation",
        default=200,
        min=1
    )
    bpy.types.Scene.s2_ao_distance = FloatProperty(
        name="Ray Distance",
        description="Maximum distance for AO ray casts",
        default=10.0,
        min=0.0
    )
    bpy.types.Scene.s2_ao_global_local_mix = FloatProperty(
        name="Global Local Mix",
        description="Blend factor between local and global AO calculations",
        default=0.5,
        min=0.0,
        max=1.0
    )
    bpy.types.Scene.s2_ao_ground_plane = BoolProperty(
        name="Ground Plane",
        description="Include a ground plane for AO calculation",
        default=False
    )
    bpy.types.Scene.s2_ao_geonode_ao = BoolProperty(
        name="Geonode AO",
        description="Use Geonode AO algorithm instead of SXAO",
        default=False
    )

_new_objects = set()

@persistent
def on_depsgraph_update(depsgraph):
    """Track objects that are added to the scene"""
    context = bpy.context
    scene = context.scene

    if not scene.s2_auto_apply_to_new:
        return

    for update in depsgraph.updates:
        if update.is_updated_geometry and hasattr(update.id, 'type') and update.id.type == 'MESH':
            obj = update.id
            if obj not in _new_objects and obj.users > 0:
                _new_objects.add(obj)
                process_new_object(context, obj)

def process_new_object(context, obj):
    """Apply UV renaming and color attribute conversion to a new object"""
    if not obj or obj.type != 'MESH' or not hasattr(obj, 'data'):
        return

    old_active = context.view_layer.objects.active
    old_selected = context.selected_objects.copy()

    for sel_obj in old_selected:
        sel_obj.select_set(False)

    obj.select_set(True)
    context.view_layer.objects.active = obj

    try:
        if not obj.data.uv_layers:
            obj.data.uv_layers.new(name="map")
        else:
            for i, uv_layer in enumerate(obj.data.uv_layers):
                uv_layer.name = "map" if i == 0 else f"map{i}"

        for attr_name in ["VertexPaintTintColor", "VertexPaintBlendParams"]:
            attr = ensure_attribute_exists(obj, attr_name, 'CORNER', 'BYTE_COLOR', 3)
            if attr_name == "VertexPaintBlendParams":
                for i in range(len(obj.data.loops)):
                    attr.data[i].color = (0.0, 0.0, 0.0, 1.0)

    except Exception as e:
        print(f"Error processing new object {obj.name}: {e}")

    finally:
        obj.select_set(False)
        for sel_obj in old_selected:
            sel_obj.select_set(True)
        context.view_layer.objects.active = old_active

def unregister_properties():
    for prop in ["s2_prefix", "s2_name", "s2_suffix", "s2_add_sizes", "s2_size_format", "s2_auto_apply_to_new", "s2_ao_attribute", "s2_ao_ray_count", "s2_ao_distance", "s2_ao_global_local_mix", "s2_ao_ground_plane", "s2_ao_geonode_ao"]:
        if hasattr(bpy.types.Scene, prop):
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
        naming_register()
        uv_attributes_register()
        ao_baking_register()

        _new_objects.clear()

        if on_depsgraph_update not in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.append(on_depsgraph_update)
    except Exception as e:
        print(f"Error registering Source 2 Utilities: {e}")
        unregister()
        raise

def unregister():
    try:
        if on_depsgraph_update in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.remove(on_depsgraph_update)
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

if __name__ == "__main__":
    register()