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
        if not scene.s2_suffix.isalpha() and not scene.s2_suffix.isdigit():
            return utils.report_error(self, "Suffix must be alphabetic or numeric")

        used_names = set()
        for obj in selected_objects:
            if obj.type != 'MESH':
                continue

            name_parts = [scene.s2_prefix, scene.s2_name]
            if scene.s2_add_sizes:
                dimensions = utils.get_object_dimensions(obj)
                size_str = utils.format_dimensions(dimensions, scene.s2_size_format)
                if size_str:
                    name_parts.append(size_str)

            # Use original suffix if preserve_suffix is enabled and object has a valid suffix
            if scene.s2_preserve_suffix and obj.name and '_' in obj.name:
                original_suffix = obj.name.split('_')[-1]
                if original_suffix.isalpha() or original_suffix.isdigit():
                    current_suffix = original_suffix
                else:
                    current_suffix = scene.s2_suffix
            else:
                current_suffix = scene.s2_suffix

            name_parts.append(current_suffix)
            new_name = "_".join(part for part in name_parts if part)

            # Handle name conflicts by incrementing suffix
            while new_name in used_names:
                current_suffix = increment_suffix(current_suffix)
                name_parts[-1] = current_suffix
                new_name = "_".join(part for part in name_parts if part)

            obj.name = new_name
            used_names.add(new_name)

        return utils.report_info(self, f"Applied naming convention to {len(selected_objects)} objects")

def increment_suffix(suffix):
    """Increment a suffix (alphabetic or numeric)."""
    if not suffix:
        return 'a'

    # Handle numeric suffix
    if suffix.isdigit():
        return str(int(suffix) + 1)

    # Handle alphabetic suffix (original logic from utils.increment_suffix)
    last_char = suffix[-1]
    rest = suffix[:-1]
    if last_char == 'z':
        return (increment_suffix(rest) + 'a') if rest else 'aa'
    return rest + chr(ord(last_char) + 1)

def naming_register():
    bpy.utils.register_class(OBJECT_OT_apply_naming_convention)
    bpy.types.Scene.s2_preserve_suffix = bpy.props.BoolProperty(
        name="Preserve Original Suffix",
        description="Keep the original suffix unless there's a name conflict",
        default=False
    )

def naming_unregister():
    try:
        bpy.utils.unregister_class(OBJECT_OT_apply_naming_convention)
        del bpy.types.Scene.s2_preserve_suffix
    except (RuntimeError, AttributeError):
        pass