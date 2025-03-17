import bpy
import bmesh
import random
from mathutils import Vector
from .. import sxao
from Source2Utilities import utils

class OBJECT_OT_bake_ao_to_selected_attribute(bpy.types.Operator):
    """
    Use the SXAO logic from sxao.py to compute an AO-like occlusion for each vertex/loop
    and bake the results into the specified color attribute for all selected mesh objects.
    """
    bl_idname = "object.bake_ao_to_selected_attribute"
    bl_label = "Bake AO (SXAO)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        # Allow operator if at least one mesh object is selected
        return any(obj.type == 'MESH' for obj in context.selected_objects)

    def execute(self, context):
        # Get all selected mesh objects
        selected_mesh_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not selected_mesh_objects:
            return utils.report_error(self, "No mesh objects selected")

        scene = context.scene
        target_attr = scene.s2_ao_attribute
        ray_count = scene.s2_ao_ray_count
        local_global_mix = scene.s2_ao_global_local_mix
        ray_distance = scene.s2_ao_distance
        ground_plane = scene.s2_ao_ground_plane
        geonode_ao = scene.s2_ao_geonode_ao

        # Save the original active object and selection state to restore later
        original_active = context.view_layer.objects.active
        original_selection = {obj: obj.select_get() for obj in context.view_layer.objects}

        # Deselect all objects first
        for obj in context.view_layer.objects:
            obj.select_set(False)

        processed_count = 0
        failed_objects = []

        # Process AO bake across each selected mesh object
        total_objects = len(selected_mesh_objects)
        self.report({'INFO'}, f"Starting AO baking on {total_objects} objects...")

        for i, obj in enumerate(selected_mesh_objects):
            # Update progress
            self.report({'INFO'}, f"Processing object {i+1}/{total_objects}: {obj.name}")

            # Set current object as active and selected
            context.view_layer.objects.active = obj
            obj.select_set(True)

            # Ensure the target color attribute exists
            attr = utils.ensure_attribute_exists(obj, target_attr, 'CORNER', 'BYTE_COLOR', 3)
            if not attr:
                failed_objects.append((obj.name, "Failed to create attribute"))
                obj.select_set(False)
                continue

            try:
                # Calculate AO colors based on the chosen method
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

                # Verify color data was computed and matches the expected length
                if not colors:
                    failed_objects.append((obj.name, "AO calculation returned no data"))
                    obj.select_set(False)
                    continue

                if len(colors) == 4 * len(obj.data.loops):
                    attr.data.foreach_set("color", colors)
                    obj.data.attributes.active_color = obj.data.attributes[target_attr]
                    processed_count += 1
                else:
                    failed_objects.append((obj.name, "Loop color array size mismatch"))
            except Exception as e:
                failed_objects.append((obj.name, str(e)))

            # Deselect current object before moving to next
            obj.select_set(False)

        # Restore original selection state
        for obj, was_selected in original_selection.items():
            obj.select_set(was_selected)

        # Restore the original active object
        context.view_layer.objects.active = original_active

        # Update viewport shading settings for all 3D Views to display vertex colors
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.shading.type = 'SOLID'
                area.spaces.active.shading.color_type = 'VERTEX'
                area.spaces.active.shading.light = 'FLAT'

        # Provide detailed feedback based on how many objects were processed successfully
        total = len(selected_mesh_objects)
        if processed_count == 0:
            error_details = "\n".join([f"- {name}: {reason}" for name, reason in failed_objects[:5]])
            if len(failed_objects) > 5:
                error_details += f"\n- ... and {len(failed_objects) - 5} more objects"
            return utils.report_error(self, f"Failed to bake AO on any objects:\n{error_details}")
        elif processed_count < total:
            failed_count = total - processed_count
            message = f"Successfully baked SXAO to '{target_attr}' on {processed_count} of {total} objects. {failed_count} objects failed."
            if failed_objects:
                message += "\nFailed objects:"
                for i, (name, reason) in enumerate(failed_objects[:3]):
                    message += f"\n- {name}: {reason}"
                if len(failed_objects) > 3:
                    message += f"\n- ... and {len(failed_objects) - 3} more objects"
            return {'WARNING'}, message
        else:
            return utils.report_info(self, f"Successfully baked SXAO to '{target_attr}' on all {processed_count} objects")

    def create_ground_plane(self, context, obj):
        """Create a temporary ground plane for AO calculation."""
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
        # Ensure the origin object remains active
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
                colors[loop_idx * 4]     = ao_val
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