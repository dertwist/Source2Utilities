bl_info = {
	"name": "ARR",
	"author": "IIIFGIII (discord IIIFGIII#7758)",
	"version": (1, 4),
	"blender": (2, 83, 0),
	"location": "View3D > N panel > FGT > ARR",
	"description": "Addon remove + reinstall by filepath",
	"warning": "",
	"wiki_url": "https://github.com/IIIFGIII/FG_Tools",
	"category": "FG_Tools",
}

import bpy
import os
import zipfile
import tempfile
import json
import re
import addon_utils
import ast

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

		# Options
		col.prop(arr, 'show_advanced', text="Advanced Options", icon='PREFERENCES')
		if arr.show_advanced:
			box = col.box()
			box.prop(arr, 'force_remove', text="Force Remove")
			box.prop(arr, 'keep_preferences', text="Keep Preferences")

		# Install button
		col.operator('fgt.arr_remove_reinstall', icon='FILE_REFRESH', text='Remove + Reinstall')

		# Status message
		if arr.status_message:
			box = col.box()
			box.label(text=arr.status_message, icon=arr.status_icon)

def get_module_name_from_py(filepath):
	"""Extract module name from a Python file."""
	# Default to filename without extension
	module_name = bpy.path.display_name_from_filepath(filepath)

	try:
		with open(filepath, 'r', encoding='utf-8') as f:
			content = f.read()
			# Use a simple regex pattern for bl_info extraction
			match = re.search(r'bl_info\s*=\s*{(.*?)}', content, re.DOTALL)
			if match:
				bl_info_str = '{' + match.group(1) + '}'
				# Convert potential single quotes or unquoted keys to JSON-like format
				bl_info_str = re.sub(r"'(\w+)':", r'"\1":', bl_info_str)
				bl_info_str = re.sub(r'(\w+):', r'"\1":', bl_info_str)

				try:
					bl_info = ast.literal_eval(bl_info_str)
					if 'name' in bl_info:
						return bl_info['name'].lower().replace(' ', '_')
				except Exception as e:
					print(f"Error parsing bl_info: {e}")
	except Exception as e:
		print(f"Error reading file: {e}")

	return module_name

def get_module_name_from_zip(filepath):
	"""Extract module name from a ZIP file."""
	try:
		with zipfile.ZipFile(filepath, 'r') as zip_ref:
			# First try: look for __init__.py at a root-level directory
			init_files = [f for f in zip_ref.namelist() if f.endswith('/__init__.py')]
			if init_files:
				module_name = os.path.dirname(init_files[0])
				if module_name:
					return module_name

			# Second try: scan for any .py file containing bl_info
			for file in zip_ref.namelist():
				if file.endswith('.py'):
					try:
						content = zip_ref.read(file).decode('utf-8')
						if 'bl_info' in content:
							match = re.search(r'bl_info\s*=\s*{(.*?)}', content, re.DOTALL)
							if match:
								bl_info_str = '{' + match.group(1) + '}'
								bl_info_str = re.sub(r"'(\w+)':", r'"\1":', bl_info_str)
								bl_info_str = re.sub(r'(\w+):', r'"\1":', bl_info_str)

								try:
									bl_info = ast.literal_eval(bl_info_str)
									if 'name' in bl_info:
										return bl_info['name'].lower().replace(' ', '_')
								except Exception as e:
									print(f"Error parsing bl_info in ZIP: {e}")
					except Exception as e:
						print(f"Error reading file from ZIP: {e}")
						continue
	except Exception as e:
		print(f"Error opening ZIP file: {e}")

	# Fallback to filename without extension
	return os.path.splitext(os.path.basename(filepath))[0]

def find_addon_by_filepath(filepath):
	"""Find an installed addon that matches the given filepath."""
	filename = os.path.basename(filepath)
	module_name = os.path.splitext(filename)[0]

	for mod in addon_utils.modules():
		if hasattr(mod, "__file__") and mod.__file__ and filename in mod.__file__:
			return mod.__name__
		if mod.__name__ == module_name or mod.__name__.endswith("." + module_name):
			return mod.__name__
	return None

class ARR_OT_Remove_Reinstall(bpy.types.Operator):
	bl_idname = 'fgt.arr_remove_reinstall'
	bl_label = 'ARR_OT_Remove_Reinstall'
	bl_options = {'REGISTER'}

	def execute(self, context):
		arr = context.scene.arr_props
		pre = bpy.ops.preferences
		filepath = bpy.path.abspath(arr.arr_path)

		# Reset status message
		arr.status_message = ""
		arr.status_icon = 'INFO'

		if not os.path.exists(filepath):
			arr.status_message = 'File path does not exist!'
			arr.status_icon = 'ERROR'
			self.report({'ERROR'}, f'File path "{arr.arr_path}" does not exist!')
			return {'CANCELLED'}

		# Check file extension
		file_ext = os.path.splitext(filepath)[1].lower()
		if arr.file_type == 'PY' and file_ext != '.py':
			arr.status_message = 'Not a Python file (.py)!'
			arr.status_icon = 'ERROR'
			self.report({'ERROR'}, 'Selected file is not a Python file (.py)!')
			return {'CANCELLED'}
		elif arr.file_type == 'ZIP' and file_ext != '.zip':
			arr.status_message = 'Not a ZIP file (.zip)!'
			arr.status_icon = 'ERROR'
			self.report({'ERROR'}, 'Selected file is not a ZIP file (.zip)!')
			return {'CANCELLED'}

		try:
			# Determine module name based on file type
			if arr.file_type == 'PY':
				module_name = get_module_name_from_py(filepath)
			else:
				module_name = get_module_name_from_zip(filepath)

			if not module_name:
				arr.status_message = 'Could not determine module name!'
				arr.status_icon = 'ERROR'
				self.report({'ERROR'}, 'Could not determine module name from file!')
				return {'CANCELLED'}

			# If the addon is already installed, get the existing module name
			existing_module = find_addon_by_filepath(filepath)
			if existing_module:
				module_name = existing_module

			# Try to remove the addon if it exists
			try:
				if arr.force_remove:
					pre.addon_disable(module=module_name)
					pre.addon_remove(module=module_name)
				else:
					is_enabled = False
					for mod in addon_utils.modules():
						if mod.__name__ == module_name:
							is_enabled = addon_utils.check(mod.__name__)[0]
							break
					if is_enabled:
						pre.addon_disable(module=module_name)
					pre.addon_remove(module=module_name)
			except Exception as e:
				print(f"Warning: Could not remove existing addon: {e}")

			# Install the addon
			result = pre.addon_install(overwrite=True, filepath=filepath)
			if 'FINISHED' not in result:
				arr.status_message = "Installation failed!"
				arr.status_icon = 'ERROR'
				self.report({'ERROR'}, f'Failed to install addon from {filepath}')
				return {'CANCELLED'}

			# Enable the addon
			if not arr.keep_preferences:
				pre.addon_enable(module=module_name)
			else:
				enabled = False
				for mod in addon_utils.modules():
					if mod.__name__ == module_name:
						try:
							addon_utils.enable(mod.__name__, default_set=False, persistent=True)
							enabled = True
							break
						except Exception as e:
							print(f"Error enabling addon with preferences: {e}")
				if not enabled:
					pre.addon_enable(module=module_name)

			arr.status_message = f'Successfully reinstalled: {module_name}'
			arr.status_icon = 'CHECKMARK'
			self.report({'INFO'}, f'Successfully reinstalled addon: {module_name}')

		except Exception as e:
			arr.status_message = f'Error: {e}'
			arr.status_icon = 'ERROR'
			self.report({'ERROR'}, f'Error during installation: {e}')
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
	show_advanced: bpy.props.BoolProperty(
		name="Show Advanced Options",
		description="Show advanced reinstallation options",
		default=False
	)
	force_remove: bpy.props.BoolProperty(
		name="Force Remove",
		description="Force remove the addon before reinstalling (may help with stubborn addons)",
		default=False
	)
	keep_preferences: bpy.props.BoolProperty(
		name="Keep Preferences",
		description="Try to keep addon preferences when reinstalling",
		default=True
	)
	status_message: bpy.props.StringProperty(
		name="Status Message",
		description="Status message from the last operation",
		default=""
	)
	status_icon: bpy.props.StringProperty(
		name="Status Icon",
		description="Icon to display with the status message",
		default="INFO"
	)

CTR = [ARR_PT_Panel, ARR_OT_Remove_Reinstall, ARR_Settings_Props]

def register():
	for cls in CTR:
		bpy.utils.register_class(cls)
	bpy.types.Scene.arr_props = bpy.props.PointerProperty(type=ARR_Settings_Props)

def unregister():
	for cls in reversed(CTR):
		bpy.utils.unregister_class(cls)
	del bpy.types.Scene.arr_props

if __name__ == "__main__":
	register()