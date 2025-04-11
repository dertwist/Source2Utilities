# Main module: Initialization, common utilities (imported from utils), panel and global handlers.
import bpy
import bmesh
import random
import math
import statistics
from mathutils import Vector
from bpy.props import StringProperty, BoolProperty, EnumProperty, IntProperty, FloatProperty, FloatVectorProperty
from bpy.types import Panel, Operator
from bpy.app.handlers import persistent

# Import common functions from the utils module
from . import utils

# Import submodules
from . import sxao
from .modules import ao_baking, naming, attributes
from .modules import color_attributes  # Color attributes module

bl_info = {
    'name': 'Source 2 Utilities',
    'author': 'Nucky3d',
    'version': (0, 6, 0),
    'blender': (3, 6, 0),
    'location': 'View3D > Source 2',
    'description': 'Utility tools for Source 2 workflows',
    'doc_url': 'https://github.com/dertwist/Source2Utilities',
    'tracker_url': '',
    'category': 'Object'
}

# ------------------
# MAIN PANEL
# ------------------
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

        # Advanced AO options
        row = box.row()
        row.prop(scene, "s2_ao_expand_advanced", text="Advanced Options",
                 icon='TRIA_DOWN' if scene.s2_ao_expand_advanced else 'TRIA_RIGHT',
                 emboss=False)

        if scene.s2_ao_expand_advanced:
            col = box.column(align=True)
            col.prop(scene, "s2_ao_intensity", text="Intensity")
            col.prop(scene, "s2_ao_contrast", text="Contrast")
            col.prop(scene, "s2_ao_bias", text="Bias")
            col.prop(scene, "s2_ao_invert", text="Invert")
            col.prop(scene, "s2_ao_tint", text="AO Tint")

        row = box.row()
        row.prop(scene, "s2_ao_ground_plane", text="Ground Plane")
        row = box.row()
        row.prop(scene, "s2_ao_geonode_ao", text="Geonode AO")
        row = box.row()
        row.operator("object.bake_ao_to_selected_attribute", text="Bake AO to Attribute")

        # The Color Attribute sub-panel will appear under the main panel as a subcategory

# ------------------
# PROPERTIES, HANDLERS, AND REGISTRATION
# ------------------

def register_properties():
    scene = bpy.types.Scene
    scene.s2_prefix = StringProperty(
        name="Name",
        description="Prefix for object naming",
        default="prop"
    )
    scene.s2_name = StringProperty(
        name="Variation",
        description="Core name for the object",
        default="01"
    )
    scene.s2_suffix = StringProperty(
        name="Suffix",
        description="Alphabetic suffix for the object",
        default="a"
    )
    scene.s2_add_sizes = BoolProperty(
        name="Include Sizes",
        description="Include object dimensions in the name",
        default=False
    )
    scene.s2_size_format = EnumProperty(
        name="Size Format",
        description="Dimensions to include in the name",
        items=[
            ('X', "X", "Include only X dimension"),
            ('Y', "Y", "Include only Y dimension"),
            ('Z', "Z", "Include only Z dimension"),
            ('XY', "XY", "Include X & Y dimensions"),
            ('XZ', "XZ", "Include X & Z dimensions"),
            ('XYZ', "XYZ", "Include X, Y & Z dimensions"),
        ],
        default='X'
    )
    scene.s2_auto_apply_to_new = BoolProperty(
        name="Auto Apply to New Objects",
        description="Automatically apply UV renaming and attribute conversion",
        default=False
    )
    scene.s2_ao_attribute = EnumProperty(
        name="AO Attribute",
        items=[
            ("VertexPaintTintColor", "Color Tint", "Bake AO into the VertexPaintTintColor attribute"),
            ("VertexPaintBlendParams", "Vertex Blend", "Bake AO into the VertexPaintBlendParams attribute"),
        ],
        default="VertexPaintTintColor",
        description="Attribute to store baked Ambient Occlusion"
    )
    scene.s2_ao_ray_count = IntProperty(
        name="Ray Count",
        description="Number of rays to use for AO calculation",
        default=64,
        min=1
    )
    scene.s2_ao_distance = FloatProperty(
        name="Ray Distance",
        description="Maximum distance for AO ray casts",
        default=10.0,
        min=0.0
    )
    scene.s2_ao_global_local_mix = FloatProperty(
        name="Global Local Mix",
        description="Blend factor between local and global AO calculations",
        default=0.5,
        min=0.0,
        max=1.0
    )
    scene.s2_ao_ground_plane = BoolProperty(
        name="Ground Plane",
        description="Include a ground plane for AO calculation",
        default=False
    )
    scene.s2_ao_geonode_ao = BoolProperty(
        name="Geonode AO",
        description="Use Geonode AO algorithm instead of SXAO",
        default=False
    )
    # New advanced AO properties
    scene.s2_ao_expand_advanced = BoolProperty(
        name="Expand Advanced Options",
        description="Show advanced AO baking options",
        default=False
    )
    scene.s2_ao_intensity = FloatProperty(
        name="Intensity",
        description="Control the strength of the AO effect",
        default=1.0,
        min=0.0,
        max=2.0
    )
    scene.s2_ao_contrast = FloatProperty(
        name="Contrast",
        description="Adjust the contrast of the AO effect",
        default=1.0,
        min=0.1,
        max=2.0
    )
    scene.s2_ao_bias = FloatProperty(
        name="Bias",
        description="Bias the AO calculation to reduce artifacts in crevices",
        default=0.0,
        min=0.0,
        max=0.5
    )
    scene.s2_ao_invert = BoolProperty(
        name="Invert",
        description="Invert the AO result",
        default=False
    )
    scene.s2_ao_tint = FloatVectorProperty(
        name="AO Tint",
        description="Tint color for Ambient Occlusion",
        subtype='COLOR',
        default=(0.0, 0.0, 0.0),
        min=0.0,
        max=1.0
    )

def unregister_properties():
    for prop in ["s2_prefix", "s2_name", "s2_suffix", "s2_add_sizes", "s2_size_format",
                "s2_auto_apply_to_new", "s2_ao_attribute", "s2_ao_ray_count",
                "s2_ao_distance", "s2_ao_global_local_mix", "s2_ao_ground_plane",
                "s2_ao_geonode_ao", "s2_ao_expand_advanced", "s2_ao_intensity",
                "s2_ao_contrast", "s2_ao_bias", "s2_ao_invert", "s2_ao_tint"]:
        if hasattr(bpy.types.Scene, prop):
            try:
                delattr(bpy.types.Scene, prop)
            except Exception:
                pass

_new_objects = set()
_processed_objects = set()

@persistent
def on_depsgraph_update(depsgraph):
    """Track objects that are added to the scene"""
    context = bpy.context
    scene = context.scene

    if not scene.s2_auto_apply_to_new:
        return

    for obj in scene.objects:
        if (obj.type == 'MESH' and
                obj not in _new_objects and
                obj not in _processed_objects and
                obj.users > 0):
            is_new = True
            if hasattr(obj, 'data') and obj.data:
                if obj.data.uv_layers and obj.data.uv_layers[0].name == "map":
                    is_new = False
                if ("VertexPaintTintColor" in obj.data.attributes and
                        "VertexPaintBlendParams" in obj.data.attributes):
                    is_new = False

            if is_new:
                _new_objects.add(obj)
                process_new_object(context, obj)
                _processed_objects.add(obj)

    for update in depsgraph.updates:
        if (update.is_updated_geometry and
                hasattr(update.id, 'type') and
                update.id.type == 'MESH'):
            obj = update.id
            if (obj not in _new_objects and
                    obj not in _processed_objects and
                    obj.users > 0):
                _new_objects.add(obj)
                process_new_object(context, obj)
                _processed_objects.add(obj)

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
            attr = utils.ensure_attribute_exists(obj, attr_name, 'CORNER', 'BYTE_COLOR', 3)
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
    for prop in ["s2_prefix", "s2_name", "s2_suffix", "s2_add_sizes", "s2_size_format",
                "s2_auto_apply_to_new", "s2_ao_attribute", "s2_ao_ray_count",
                "s2_ao_distance", "s2_ao_global_local_mix", "s2_ao_ground_plane",
                "s2_ao_geonode_ao", "s2_ao_expand_advanced", "s2_ao_intensity",
                "s2_ao_contrast", "s2_ao_bias", "s2_ao_invert"]:
        if hasattr(bpy.types.Scene, prop):
            try:
                delattr(bpy.types.Scene, prop)
            except Exception:
                pass

# ------------------
# REGISTER / UNREGISTER
# ------------------
def register():
    try:
        register_properties()
        bpy.utils.register_class(VIEW3D_PT_source2_utilities)
        naming.naming_register()
        attributes.attributes_register()
        ao_baking.ao_baking_register()
        color_attributes.register()  # Register color attributes module
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
    for unregister_func in (ao_baking.ao_baking_unregister, attributes.attributes_unregister, naming.naming_unregister, color_attributes.unregister):
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