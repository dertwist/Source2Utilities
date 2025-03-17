# utils module: Contains common utility functions for Source2Utilities
import bpy
import bmesh
import math
import statistics
from mathutils import Vector
from bpy.props import StringProperty, BoolProperty, EnumProperty, IntProperty, FloatProperty

def get_override(context, obj):
    """Return an override dictionary including area and region from a 3D View, if available."""
    override = context.copy()
    for area in context.screen.areas:
        if area.type == "VIEW_3D":
            override["area"] = area
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