# AO Baking module: Contains AO baking operator and related registration.
import bpy
import bmesh
import random
from mathutils import Vector
from .. import sxao
from Source2Utilities import utils

class OBJECT_OT_bake_ao_to_selected_attribute(bpy.types.Operator):
    """
    Use the SXAO logic from sxao.py to compute an AO-like occlusion for each vertex/loop.
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
            return utils.report_error(self, "No mesh object selected")
        scene = context.scene
        target_attr = scene.s2_ao_attribute
        ray_count = scene.s2_ao_ray_count
        local_global_mix = scene.s2_ao_global_local_mix
        ray_distance = scene.s2_ao_distance
        ground_plane = scene.s2_ao_ground_plane
        geonode_ao = scene.s2_ao_geonode_ao
        attr = utils.ensure_attribute_exists(obj, target_attr, 'CORNER', 'BYTE_COLOR', 3)
        if not attr:
            return utils.report_error(self, f"Failed to create '{target_attr}' attribute")
        if geonode_ao:
            colors = self.calculate_geonode_ao(obj, ray_count, local_global_mix, ray_distance, ground_plane)
        else:
            generator = sxao.SXAO_generate()
            temp_plane = None
            if ground_plane:
                temp_plane = self.create_ground_plane(context, obj)
            colors = generator.occlusion_list(obj, raycount=ray_count, blend=local_global_mix, dist=ray_distance, groundplane=ground_plane)
            if temp_plane:
                bpy.data.objects.remove(temp_plane, do_unlink=True)
        if not colors:
            return utils.report_error(self, "AO calculation returned no data")
        if len(colors) == 4 * len(obj.data.loops):
            attr.data.foreach_set("color", colors)
        else:
            return utils.report_error(self, "Loop color array size mismatch")
        obj.data.attributes.active_color = obj.data.attributes[target_attr]
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.shading.type = 'SOLID'
                area.spaces.active.shading.color_type = 'VERTEX'
                area.spaces.active.shading.light = 'FLAT'
        return utils.report_info(self, f"Successfully baked SXAO to '{target_attr}'")

    def create_ground_plane(self, context, obj):
        """Create a temporary ground plane for AO calculation"""
        utils_sxao = sxao.SXAO_utils()
        xmin, xmax, ymin, ymax, zmin, _ = utils_sxao.get_object_bounding_box([obj])
        plane_size = max(xmax - xmin, ymax - ymin) * 3
        plane_z = zmin - 0.001
        bpy.ops.mesh.primitive_plane_add(
            size=plane_size,
            location=((xmax + xmin) / 2, (ymax + ymin) / 2, plane_z)
        )
        plane = context.active_object
        plane.name = "SXAO_TempGroundPlane"
        plane.hide_render = True
        plane.hide_viewport = False
        plane.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        return plane

    def calculate_geonode_ao(self, obj, ray_count, blend, distance, ground_plane):
        """Calculate AO using a placeholder Geometry Nodes approach."""
        mesh = obj.data
        loop_count = len(mesh.loops)
        colors = [0.0] * (4 * loop_count)
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.normal_update()
        world_matrix = obj.matrix_world
        vert_ao = {}
        for v in bm.verts:
            pos = world_matrix @ v.co
            normal = (world_matrix.to_3x3() @ v.normal).normalized()
            ao_value = 1.0
            for i in range(ray_count):
                ray_dir = normal.copy()
                ray_dir.x += (random.random() - 0.5) * 0.8
                ray_dir.y += (random.random() - 0.5) * 0.8
                ray_dir.z += (random.random() - 0.5) * 0.8
                ray_dir.normalize()
                if ray_dir.dot(normal) > 0:
                    hit, _, _, _ = obj.ray_cast(pos + normal * 0.001, ray_dir, distance=distance)
                    if hit:
                        ao_value -= 1.0 / ray_count
            if ground_plane and pos.z < 0.1:
                ground_factor = 1.0 - min(1.0, pos.z / 0.1)
                ao_value *= (1.0 - ground_factor * 0.5)
            vert_ao[v.index] = max(0.0, min(1.0, ao_value))
        for face in bm.faces:
            for loop in face.loops:
                loop_idx = loop.index
                ao_val = vert_ao.get(loop.vert.index, 1.0)
                colors[loop_idx * 4] = ao_val
                colors[loop_idx * 4 + 1] = ao_val
                colors[loop_idx * 4 + 2] = ao_val
                colors[loop_idx * 4 + 3] = 1.0
        bm.free()
        return colors

def ao_baking_register():
    bpy.utils.register_class(OBJECT_OT_bake_ao_to_selected_attribute)

def ao_baking_unregister():
    try:
        bpy.utils.unregister_class(OBJECT_OT_bake_ao_to_selected_attribute)
    except RuntimeError:
        pass