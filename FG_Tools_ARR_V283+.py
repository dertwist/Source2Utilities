bl_info = {
	"name": "ARR",
	"author": "IIIFGIII (discord IIIFGIII#7758)",
	"version": (1, 3),
	"blender": (2, 83, 0),
	"location": "Viev3D > N panel > FGT > ARR",
	"description": "Addon remove + reinstall by filepath",
	"warning": "",
	"wiki_url": "https://github.com/IIIFGIII/FG_Tools",
	"category": "FG_Tools",
}

import bpy
import os

class ARR_PT_Panel(bpy.types.Panel):
	bl_label = 'ARR'
	bl_idname = 'ARR_PT_Panel'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'FGT'
	bl_options = {'DEFAULT_CLOSED'}

	def draw(self, context):
		arr = context.scene.arr_props
		layout = self.layout
		col = layout.column(align=True)

		# File path selection
		col.label(text="Select addon file:")
		row = col.row(align=True)
		row.prop(arr, 'arr_path', text='')

		# File type filter
		col.prop(arr, 'file_type', text="File Type")

		# Install button
		col.operator('fgt.arr_remove_reinstall', icon='FILE_REFRESH', text='Remove + Reinstall')


class ARR_OT_Remove_Reinstall(bpy.types.Operator):
	bl_idname = 'fgt.arr_remove_reinstall'
	bl_label = 'ARR_OT_Remove_Reinstall'
	bl_options = {'REGISTER'}

	def execute(self, context):
		arr = context.scene.arr_props
		pre = bpy.ops.preferences
		filepath = bpy.path.abspath(arr.arr_path)

		# Check if file exists
		if not os.path.exists(filepath):
			self.report({'ERROR'}, f'File path "{arr.arr_path}" does not exist!')
			return {'CANCELLED'}

		# Check file extension
		file_ext = os.path.splitext(filepath)[1].lower()
		if arr.file_type == 'PY' and file_ext != '.py':
			self.report({'ERROR'}, f'Selected file is not a Python file (.py)!')
			return {'CANCELLED'}
		elif arr.file_type == 'ZIP' and file_ext != '.zip':
			self.report({'ERROR'}, f'Selected file is not a ZIP file (.zip)!')
			return {'CANCELLED'}

		try:
			# Install the addon
			pre.addon_install(overwrite=True, filepath=filepath)

			# Enable the addon (different handling for py vs zip)
			if arr.file_type == 'PY':
				module_name = bpy.path.display_name_from_filepath(filepath)
			else:  # ZIP file
				# For zip files, we need to extract the module name from the zip filename
				module_name = os.path.splitext(os.path.basename(filepath))[0]

			pre.addon_enable(module=module_name)
			self.report({'INFO'}, f'Successfully reinstalled addon: {module_name}')

		except Exception as e:
			self.report({'ERROR'}, f'Error during installation: {str(e)}')
			return {'CANCELLED'}

		return {'FINISHED'}


class ARR_Settings_Props(bpy.types.PropertyGroup):
	arr_path: bpy.props.StringProperty(
		name="Addon File",
		description="Path to the addon file (.py or .zip)",
		default='',
		subtype='FILE_PATH'
	)

	file_type: bpy.props.EnumProperty(
		name="File Type",
		description="Type of addon file to install",
		items=[
			('PY', "Python File (.py)", "Select a Python file"),
			('ZIP', "ZIP Archive (.zip)", "Select a ZIP archive")
		],
		default='PY'
	)


CTR = [ARR_PT_Panel, ARR_OT_Remove_Reinstall, ARR_Settings_Props]

def register():
	for cls in CTR:
		bpy.utils.register_class(cls)
	# Register properties
	bpy.types.Scene.arr_props = bpy.props.PointerProperty(type=ARR_Settings_Props)

def unregister():
	for cls in reversed(CTR):
		bpy.utils.unregister_class(cls)
	# Delete properties
	del bpy.types.Scene.arr_props