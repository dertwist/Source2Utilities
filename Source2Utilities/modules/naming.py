# Naming module: Contains naming operator and related registration.
import bpy
from Source2Utilities import utils

class OBJECT_OT_apply_naming_convention(bpy.types.Operator):
    """Apply the Source 2 naming convention to selected objects."""
    bl_idname = "object.apply_naming_convention"
    bl_label = "Apply Naming Convention"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        selected_objects = context.selected_objects
        if not selected_objects:
            return utils.report_error(self, "No objects selected")
        if not scene.s2_suffix.isalpha():
            return utils.report_error(self, "Suffix must be alphabetic")
        used_names = set()
        current_suffix = scene.s2_suffix
        for obj in selected_objects:
            if obj.type != 'MESH':
                continue
            name_parts = [scene.s2_prefix, scene.s2_name]
            if scene.s2_add_sizes:
                dimensions = utils.get_object_dimensions(obj)
                size_str = utils.format_dimensions(dimensions, scene.s2_size_format)
                if size_str:
                    name_parts.append(size_str)
            name_parts.append(current_suffix)
            new_name = "_".join(part for part in name_parts if part)
            while new_name in used_names:
                current_suffix = utils.increment_suffix(current_suffix)
                name_parts[-1] = current_suffix
                new_name = "_".join(part for part in name_parts if part)
            obj.name = new_name
            used_names.add(new_name)
            current_suffix = utils.increment_suffix(current_suffix)
        return utils.report_info(self, f"Applied naming convention to {len(selected_objects)} objects")

def naming_register():
    bpy.utils.register_class(OBJECT_OT_apply_naming_convention)

def naming_unregister():
    try:
        bpy.utils.unregister_class(OBJECT_OT_apply_naming_convention)
    except RuntimeError:
        pass