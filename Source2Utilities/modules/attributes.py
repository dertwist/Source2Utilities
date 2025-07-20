# Attributes module: Contains UV map renaming and color attribute conversion operators.
import bpy
from Source2Utilities import utils

class OBJECT_OT_rename_uv_maps(bpy.types.Operator):
    """Rename UV maps to match Source 2 format (map, map1, map2, etc.)."""
    bl_idname = "object.rename_uv_maps"
    bl_label = "Rename UV Maps"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(obj.type == 'MESH' for obj in context.selected_objects)

    def execute(self, context):
        selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not selected_meshes:
            return utils.report_error(self, "No mesh objects selected")
        
        processed_count = 0
        created_count = 0
        
        for obj in selected_meshes:
            if not obj.data.uv_layers:
                obj.data.uv_layers.new(name="map")
                created_count += 1
            else:
                for i, uv_layer in enumerate(obj.data.uv_layers):
                    uv_layer.name = "map" if i == 0 else f"map{i}"
                processed_count += 1
        
        if created_count > 0 and processed_count > 0:
            return utils.report_info(self, f"Processed {processed_count} objects, created UV maps for {created_count} objects")
        elif created_count > 0:
            return utils.report_info(self, f"Created new UV maps named 'map' for {created_count} objects")
        else:
            return utils.report_info(self, f"Renamed UV maps to Source 2 format for {processed_count} objects")

class OBJECT_OT_convert_color_attributes(bpy.types.Operator):
    """
    Convert color attributes to Source 2 format.
    (This converts attributes to use CORNER domain and BYTE_COLOR data type.)
    """
    bl_idname = "object.convert_color_attributes"
    bl_label = "Convert Color Attributes"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(obj.type == 'MESH' for obj in context.selected_objects)

    def execute(self, context):
        selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not selected_meshes:
            return utils.report_error(self, "No mesh objects selected")
        
        target_attributes = ["VertexPaintTintColor", "VertexPaintBlendParams"]
        total_converted = 0
        total_created = 0
        processed_objects = 0
        
        for obj in selected_meshes:
            converted_count = 0
            created_count = 0
            
            for attr_name in target_attributes:
                if attr_name in obj.data.attributes:
                    attr = obj.data.attributes[attr_name]
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
                    new_attr = utils.ensure_attribute_exists(obj, attr_name, 'CORNER', 'BYTE_COLOR', 3)
                    for i, loop in enumerate(obj.data.loops):
                        if i < len(temp_data):
                            new_attr.data[i].color = temp_data[i][:3] + (1.0,)
                    converted_count += 1
                else:
                    new_attr = utils.ensure_attribute_exists(obj, attr_name, 'CORNER', 'BYTE_COLOR', 3)
                    if attr_name == "VertexPaintBlendParams":
                        for i in range(len(obj.data.loops)):
                            new_attr.data[i].color = (0.0, 0.0, 0.0, 1.0)
                    created_count += 1
            
            total_converted += converted_count
            total_created += created_count
            processed_objects += 1
        
        msg = f"Processed {processed_objects} objects: {total_converted} attributes converted, {total_created} attributes created"
        return utils.report_info(self, msg)

def attributes_register():
    bpy.utils.register_class(OBJECT_OT_rename_uv_maps)
    bpy.utils.register_class(OBJECT_OT_convert_color_attributes)

def attributes_unregister():
    for cls in (OBJECT_OT_convert_color_attributes, OBJECT_OT_rename_uv_maps):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass