
import bpy
from Source2Utilities import utils

def get_obj_prop(obj, prop, scene_default):
    """Get per-object property if set, else scene default."""
    return obj.get(f"s2_{prop}", getattr(bpy.context.scene, f"s2_{prop}", scene_default))

def set_obj_prop(obj, prop, value):
    obj[f"s2_{prop}"] = value

def clear_obj_prop(obj, prop):
    obj.pop(f"s2_{prop}", None)

def get_multi_value(objects, prop, scene_default):
    """Return value if all objects have the same, else None."""
    values = {get_obj_prop(obj, prop, scene_default) for obj in objects}
    return values.pop() if len(values) == 1 else None

def get_object_dimensions_any(obj):
    """Get object's bounding-box dimensions in centimeters."""
    scale = bpy.context.scene.unit_settings.scale_length
    if hasattr(obj.data, "vertices"):
        coords = [obj.matrix_world @ v.co for v in obj.data.vertices]
    elif hasattr(obj, "bound_box") and obj.bound_box:
        coords = [obj.matrix_world @ bpy.mathutils.Vector(corner) for corner in obj.bound_box]
    else:
        coords = [obj.matrix_world.translation]
    if not coords:
        return (0, 0, 0)
    xs, ys, zs = zip(*[(v.x, v.y, v.z) for v in coords])
    return (
        int(round((max(xs) - min(xs)) * scale * 100)),
        int(round((max(ys) - min(ys)) * scale * 100)),
        int(round((max(zs) - min(zs)) * scale * 100)),
    )

class OBJECT_OT_set_custom_naming(bpy.types.Operator):
    """Set custom naming fields for selected objects."""
    bl_idname = "object.set_custom_naming"
    bl_label = "Set Custom Naming"
    bl_options = {'REGISTER', 'UNDO'}

    s2_prefix: bpy.props.StringProperty(name="Prefix")
    s2_name: bpy.props.StringProperty(name="Name")
    s2_suffix: bpy.props.StringProperty(name="Suffix")

    def invoke(self, context, event):
        selected = context.selected_objects
        scene = context.scene
        self.s2_prefix = get_multi_value(selected, "prefix", scene.s2_prefix) or ""
        self.s2_name = get_multi_value(selected, "name", scene.s2_name) or ""
        self.s2_suffix = get_multi_value(selected, "suffix", scene.s2_suffix) or ""
        self._multi_prefix = get_multi_value(selected, "prefix", scene.s2_prefix) is None
        self._multi_name = get_multi_value(selected, "name", scene.s2_name) is None
        self._multi_suffix = get_multi_value(selected, "suffix", scene.s2_suffix) is None
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        if self._multi_prefix:
            layout.label(text="multiple values", icon='ERROR')
        layout.prop(self, "s2_prefix")
        if self._multi_name:
            layout.label(text="multiple values", icon='ERROR')
        layout.prop(self, "s2_name")
        if self._multi_suffix:
            layout.label(text="multiple values", icon='ERROR')
        layout.prop(self, "s2_suffix")

    def execute(self, context):
        for obj in context.selected_objects:
            set_obj_prop(obj, "prefix", self.s2_prefix)
            set_obj_prop(obj, "name", self.s2_name)
            set_obj_prop(obj, "suffix", self.s2_suffix)
        return {'FINISHED'}

class OBJECT_OT_apply_naming_convention(bpy.types.Operator):
    """Apply naming convention to selected objects. Group instance children are skipped."""
    bl_idname = "object.apply_naming_convention"
    bl_label = "Apply Naming Convention"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        selected = context.selected_objects
        if not selected:
            return utils.report_error(self, "No objects selected")
        all_names = {obj.name for obj in bpy.context.scene.objects}

        for obj in selected:
            # Only rename group instance itself, not its children
            if obj.type == 'EMPTY' and getattr(obj, "instance_collection", None):
                pass  # Rename the group instance itself
            elif getattr(obj, "parent", None) and obj.parent in selected:
                if obj.parent.type == 'EMPTY' and getattr(obj.parent, "instance_collection", None):
                    continue  # Skip children of selected group instance

            prefix = get_obj_prop(obj, "prefix", scene.s2_prefix)
            name = get_obj_prop(obj, "name", scene.s2_name)
            suffix = get_obj_prop(obj, "suffix", scene.s2_suffix)
            if not (suffix.isalpha() or suffix.isdigit()):
                suffix = scene.s2_suffix

            name_parts = [prefix, name]
            if getattr(scene, "s2_add_sizes", False):
                dims = get_object_dimensions_any(obj)
                size_str = utils.format_dimensions(dims, getattr(scene, "s2_size_format", "XYZ"))
                if size_str:
                    name_parts.append(size_str)

            if getattr(scene, "s2_preserve_suffix", False) and obj.name and '_' in obj.name:
                orig_suffix = obj.name.split('_')[-1]
                current_suffix = orig_suffix if (orig_suffix.isalpha() or orig_suffix.isdigit()) else suffix
            else:
                current_suffix = suffix

            name_parts.append(current_suffix)
            new_name = "_".join(part for part in name_parts if part)
            while new_name in all_names:
                current_suffix = increment_suffix(current_suffix)
                name_parts[-1] = current_suffix
                new_name = "_".join(part for part in name_parts if part)
            obj.name = new_name
            all_names.add(new_name)

        return utils.report_info(self, f"Applied naming convention to {len(selected)} objects")

def increment_suffix(suffix):
    """Increment a suffix (alphabetic or numeric)."""
    if not suffix:
        return 'a'
    if suffix.isdigit():
        return str(int(suffix) + 1)
    last_char = suffix[-1]
    rest = suffix[:-1]
    if last_char == 'z':
        return (increment_suffix(rest) + 'a') if rest else 'aa'
    return rest + chr(ord(last_char) + 1)

def naming_register():
    bpy.utils.register_class(OBJECT_OT_apply_naming_convention)
    bpy.utils.register_class(OBJECT_OT_set_custom_naming)
    bpy.types.Scene.s2_preserve_suffix = bpy.props.BoolProperty(
        name="Preserve Original Suffix",
        description="Keep the original suffix unless there's a name conflict",
        default=False
    )

def naming_unregister():
    try:
        bpy.utils.unregister_class(OBJECT_OT_apply_naming_convention)
        bpy.utils.unregister_class(OBJECT_OT_set_custom_naming)
        del bpy.types.Scene.s2_preserve_suffix
    except Exception:
        pass
