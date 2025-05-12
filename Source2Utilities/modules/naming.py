
import bpy
from Source2Utilities import utils

# --- Per-object custom property helpers ---

def get_obj_prop(obj, prop, scene_default):
    """Get per-object property if set, else scene default."""
    return obj.get(f"s2_{prop}", getattr(bpy.context.scene, f"s2_{prop}", scene_default))

def set_obj_prop(obj, prop, value):
    obj[f"s2_{prop}"] = value

def clear_obj_prop(obj, prop):
    if f"s2_{prop}" in obj:
        del obj[f"s2_{prop}"]

def get_multi_value(objects, prop, scene_default):
    """Return value if all objects have the same, else None."""
    values = {get_obj_prop(obj, prop, scene_default) for obj in objects}
    if len(values) == 1:
        return values.pop()
    return None

# --- Operator for multi-editing prefix, name, suffix ---

class OBJECT_OT_set_custom_naming(bpy.types.Operator):
    """Set custom naming fields for selected objects (multi-editing supported)."""
    bl_idname = "object.set_custom_naming"
    bl_label = "Set Custom Naming"
    bl_options = {'REGISTER', 'UNDO'}

    s2_prefix: bpy.props.StringProperty(name="Prefix")
    s2_name: bpy.props.StringProperty(name="Name")
    s2_suffix: bpy.props.StringProperty(name="Suffix")

    def invoke(self, context, event):
        selected = context.selected_objects
        scene = context.scene
        # Show "multiple values" if not all the same
        prefix = get_multi_value(selected, "prefix", scene.s2_prefix)
        name = get_multi_value(selected, "name", scene.s2_name)
        suffix = get_multi_value(selected, "suffix", scene.s2_suffix)
        self.s2_prefix = prefix if prefix is not None else ""
        self.s2_name = name if name is not None else ""
        self.s2_suffix = suffix if suffix is not None else ""
        self._multi_prefix = prefix is None
        self._multi_name = name is None
        self._multi_suffix = suffix is None
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
        selected = context.selected_objects
        for obj in selected:
            set_obj_prop(obj, "prefix", self.s2_prefix)
            set_obj_prop(obj, "name", self.s2_name)
            set_obj_prop(obj, "suffix", self.s2_suffix)
        # Optionally, update names immediately
        bpy.ops.object.apply_naming_convention()
        return {'FINISHED'}

# --- Naming convention operator ---

class OBJECT_OT_apply_naming_convention(bpy.types.Operator):
    """Apply the Source 2 naming convention to selected objects, ensuring global uniqueness."""
    bl_idname = "object.apply_naming_convention"
    bl_label = "Apply Naming Convention"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        selected_objects = context.selected_objects
        if not selected_objects:
            return utils.report_error(self, "No objects selected")

        # Gather all names in the scene to ensure global uniqueness
        all_scene_names = {obj.name for obj in bpy.context.scene.objects}

        for obj in selected_objects:
            if obj.type != 'MESH':
                continue

            prefix = get_obj_prop(obj, "prefix", scene.s2_prefix)
            name = get_obj_prop(obj, "name", scene.s2_name)
            suffix = get_obj_prop(obj, "suffix", scene.s2_suffix)

            # Validate suffix
            if not suffix.isalpha() and not suffix.isdigit():
                suffix = scene.s2_suffix

            name_parts = [prefix, name]
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
                    current_suffix = suffix
            else:
                current_suffix = suffix

            name_parts.append(current_suffix)
            new_name = "_".join(part for part in name_parts if part)

            # Ensure global uniqueness (avoid .001, .002, etc.)
            while new_name in all_scene_names:
                current_suffix = increment_suffix(current_suffix)
                name_parts[-1] = current_suffix
                new_name = "_".join(part for part in name_parts if part)
            obj.name = new_name
            all_scene_names.add(new_name)

        return utils.report_info(self, f"Applied naming convention to {len(selected_objects)} objects")

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

# --- Dynamic update handler with recursion guard ---

_naming_update_in_progress = False

def update_names_on_selection(scene):
    global _naming_update_in_progress
    if _naming_update_in_progress:
        return
    _naming_update_in_progress = True
    try:
        selected = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
        if not selected:
            return
        bpy.ops.object.apply_naming_convention()
    finally:
        _naming_update_in_progress = False

def naming_register():
    bpy.utils.register_class(OBJECT_OT_apply_naming_convention)
    bpy.utils.register_class(OBJECT_OT_set_custom_naming)
    bpy.types.Scene.s2_preserve_suffix = bpy.props.BoolProperty(
        name="Preserve Original Suffix",
        description="Keep the original suffix unless there's a name conflict",
        default=False
    )
    # Add handler for dynamic update
    if update_names_on_selection not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(update_names_on_selection)

def naming_unregister():
    try:
        bpy.utils.unregister_class(OBJECT_OT_apply_naming_convention)
        bpy.utils.unregister_class(OBJECT_OT_set_custom_naming)
        del bpy.types.Scene.s2_preserve_suffix
        # Remove handler
        if update_names_on_selection in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.remove(update_names_on_selection)
    except (RuntimeError, AttributeError, ValueError):
        pass
