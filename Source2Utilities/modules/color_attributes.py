"""
Module: color_attributes.py

Purpose:
    Tools for managing color attributes, including flat shading toggling and color filling for objects and selected faces.

Features:
    • Flat Shading Toggle: Button toggles viewport shading to show vertex colors.
    • Color Fill Buttons: Blue, Red, Green, White, Black; fills selected faces (Edit Mode) or entire object (Object Mode).
    • Custom Color Picker: Color picker with "Apply Color" button.

Implementation:
    • Module: This file is placed at /Source2Utilities/modules/color_attributes.py.
    • Logic: Applies colors to the selected attribute based on current mode.
    • UI: Provides attribute selector, flat shading toggle, preset fill buttons, and custom color picker.
"""

import bpy
import bmesh
from bpy.props import FloatVectorProperty, EnumProperty, BoolProperty
from bpy.types import Operator, Panel
from Source2Utilities import utils

# Global variable to store previous shading settings
shading_preserve = ['SOLID', 'MATCAP', 'MATERIAL', False]

# ----------------------------------------------------------------
# Helper Function: apply_color
# ----------------------------------------------------------------
def apply_color(obj, attr_name, color_tuple):
    """
    Applies the specified color to the object's color attribute.
    In Edit Mode, applies the color only to selected faces.
    In Object Mode, applies the color to all loops.

    Parameters:
         obj: active mesh object.
         attr_name: name of the color attribute.
         color_tuple: tuple of 3 floats (RGB); alpha defaults to 1.0.
    """
    rgba = (*color_tuple, 1.0)  # Ensure alpha=1.0
    mode = bpy.context.mode

    if mode == 'EDIT_MESH':
        # Use bmesh for edit mode operations
        mesh = obj.data
        bm = bmesh.from_edit_mesh(mesh)

        # Get or create a color layer in bmesh with the name matching the attribute
        color_layer = bm.loops.layers.color.get(attr_name)
        if color_layer is None:
            color_layer = bm.loops.layers.color.new(attr_name)

        # Apply the color only to selected faces
        for face in bm.faces:
            if face.select:
                for loop in face.loops:
                    loop[color_layer] = rgba

        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)

    else:
        # Object mode: fill the color attribute for the entire object
        mesh = obj.data

        # Ensure the attribute exists
        if attr_name not in mesh.attributes:
            # Create the attribute with BYTE_COLOR type and CORNER domain
            mesh.attributes.new(name=attr_name, type='BYTE_COLOR', domain='CORNER')
        color_attribute = mesh.attributes[attr_name]

        # Apply color to all loops
        for i in range(len(mesh.loops)):
            color_attribute.data[i].color = rgba


# ----------------------------------------------------------------
# Operators
# ----------------------------------------------------------------

class OBJECT_OT_fill_color_attribute(Operator):
    """Fill the selected attribute with a specified color on selected faces (Edit Mode) or the whole object (Object Mode)"""
    bl_idname = "object.fill_color_attribute"
    bl_label = "Fill Color Attribute"
    bl_options = {'REGISTER', 'UNDO'}

    fill_color: FloatVectorProperty(
        name="Fill Color",
        subtype='COLOR',
        size=3,
        default=(1.0, 1.0, 1.0)
    )

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return utils.report_error(self, "No mesh object selected")

        # Get target attribute from scene property
        attr_name = context.scene.s2_selected_color_attribute

        # Apply the color using helper function
        apply_color(obj, attr_name, self.fill_color)
        return {'FINISHED'}


class OBJECT_OT_toggle_flat_shading(Operator):
    """Toggle between Flat Attributes and Studio Object shading modes"""
    bl_idname = "object.toggle_flat_shading"
    bl_label = "Flat Shading (Attribute)"
    bl_options = {'REGISTER', 'UNDO'}

    switch_to_flat: BoolProperty(
        name="Switch to Flat",
        default=True,
        description="Toggle between flat shading and previous shading"
    )

    # The line causing the error was here - a reference to 'bpr.IntProperty'
    # It has been removed

    def execute(self, context):
        global shading_preserve

        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return utils.report_error(self, "No mesh object selected")

        # Find the 3D view
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                shading = area.spaces.active.shading

                # Toggle between flat shading and previous settings
                if shading.light == 'FLAT' and shading.color_type == 'VERTEX':
                    # Restore previous settings
                    if shading_preserve[0] != 'SOLID':
                        shading.type = shading_preserve[0]
                    else:
                        shading.type = 'SOLID'

                    shading.light = shading_preserve[1]
                    shading.color_type = shading_preserve[2]
                else:
                    # Save current settings
                    shading_preserve[0] = shading.type
                    shading_preserve[1] = shading.light
                    shading_preserve[2] = shading.color_type

                    # Switch to flat shading with vertex colors
                    shading.type = 'SOLID'
                    shading.light = 'FLAT'
                    shading.color_type = 'VERTEX'

                    # Set the active color attribute
                    if context.scene.s2_selected_color_attribute in obj.data.attributes:
                        obj.data.attributes.active_color = obj.data.attributes[context.scene.s2_selected_color_attribute]

                break

        return {'FINISHED'}


# ----------------------------------------------------------------
# UI Panel
# ----------------------------------------------------------------

class VIEW3D_PT_color_attributes(Panel):
    """Sub-category panel for color attribute management."""
    bl_label = "Color Attribute"
    bl_idname = "VIEW3D_PT_color_attributes"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Source 2'
    bl_parent_id = "VIEW3D_PT_source2_utilities"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # Attribute selection dropdown
        layout.prop(scene, "s2_selected_color_attribute", text="Attribute")

        # Toggle button for flat shading
        layout.operator("object.toggle_flat_shading",
                        text="Flat Shading (Attribute)",
                        icon='SHADING_RENDERED')

        layout.separator()
        layout.label(text="Preset Color Fill:")

        # Row: Preset fill buttons for Blue, Red, Green
        row = layout.row(align=True)
        op_blue = row.operator("object.fill_color_attribute", text="Blue", icon='COLOR')
        op_blue.fill_color = (0.0, 0.0, 1.0)
        op_red = row.operator("object.fill_color_attribute", text="Red", icon='COLOR')
        op_red.fill_color = (1.0, 0.0, 0.0)
        op_green = row.operator("object.fill_color_attribute", text="Green", icon='COLOR')
        op_green.fill_color = (0.0, 1.0, 0.0)

        # Row: Preset fill buttons for White and Black
        row = layout.row(align=True)
        op_white = row.operator("object.fill_color_attribute", text="White", icon='COLOR')
        op_white.fill_color = (1.0, 1.0, 1.0)
        op_black = row.operator("object.fill_color_attribute", text="Black", icon='COLOR')
        op_black.fill_color = (0.0, 0.0, 0.0)

        layout.separator()
        layout.label(text="Custom Color Fill:")

        # Custom color picker
        layout.prop(scene, "s2_custom_color", text="Color Picker")

        # Apply custom color button
        op_custom = layout.operator("object.fill_color_attribute", text="Apply Color", icon='CHECKMARK')
        op_custom.fill_color = scene.s2_custom_color


# ----------------------------------------------------------------
# Registration
# ----------------------------------------------------------------

classes = (
    OBJECT_OT_fill_color_attribute,
    OBJECT_OT_toggle_flat_shading,
    VIEW3D_PT_color_attributes,
)

def register_properties():
    """Register scene properties for custom color and attribute selection."""
    scene = bpy.types.Scene

    # Custom color property
    scene.s2_custom_color = FloatVectorProperty(
        name="Custom Color",
        subtype='COLOR',
        size=3,
        default=(1.0, 0.5, 0.0),
        description="Select a custom fill color"
    )

    # Color attribute selection property
    scene.s2_selected_color_attribute = EnumProperty(
        name="Color Attribute",
        items=[
            ("VertexPaintTintColor", "Color Tint", "Use VertexPaintTintColor attribute"),
            ("VertexPaintBlendParams", "Vertex Blend", "Use VertexPaintBlendParams attribute")
        ],
        default="VertexPaintTintColor",
        description="Select the color attribute to modify"
    )

def unregister_properties():
    """Unregister the custom scene properties."""
    props = ("s2_custom_color", "s2_selected_color_attribute")
    for prop in props:
        if hasattr(bpy.types.Scene, prop):
            try:
                delattr(bpy.types.Scene, prop)
            except Exception:
                pass

def register():
    """Register all classes and properties in this module."""
    for cls in classes:
        bpy.utils.register_class(cls)
    register_properties()

def unregister():
    """Unregister all classes and properties in this module."""
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    unregister_properties()

__all__ = ["register", "unregister"]