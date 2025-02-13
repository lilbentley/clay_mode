bl_info = {
    "name": "clay_mode",
    "description": "Simplifies enabling/disabling material override in the View Layer.",
    "author": "Tjomma",
    "version": (1, 4, 0),
    "blender": (4, 2, 2),
    "category": "Material"
}

# Attempt 1

import bpy
from . import addon_updater_ops
import sys
import subprocess
from mathutils import Vector

def ensure_dependencies():
    try:
        import google.generativeai  # Check if library is installed
    except ModuleNotFoundError:
        # Attempt to install the library in Blender's Python environment
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "google-generativeai"])
            import google.generativeai  # Re-import after installation
        except Exception as e:
            print(f"Failed to install google-generativeai: {e}")
            raise ModuleNotFoundError("google-generativeai is not installed and could not be installed.")
        
def create_clay_material():
    """Create a material for architectural visualization:
    - White Principled BSDF for default objects (Object Index = 0)
    - Glass BSDF for objects with Object Index > 0.5
    """
    mat = bpy.data.materials.new(name="M_ClayMode_Override")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    # Clear default nodes
    nodes.clear()

    # Create Principled BSDF (Default White Material)
    principled = nodes.new('ShaderNodeBsdfPrincipled')
    principled.inputs['Base Color'].default_value = (1, 1, 1, 1)  # White
    principled.inputs['Roughness'].default_value = 0.8  # Smooth surface

    # Create Glass BSDF (Translucent Material)
    glass = nodes.new('ShaderNodeBsdfGlass')
    glass.inputs['Color'].default_value = (1, 1, 1, 1)  # Clear glass
    glass.inputs['Roughness'].default_value = 0.05  # Smooth glass

    # Create Mix Shader to blend Principled and Glass
    mix_shader = nodes.new('ShaderNodeMixShader')

    # Create Object Info Node to get Object Index
    object_info = nodes.new('ShaderNodeObjectInfo')

    # Create Math Node to compare Object Index to 0.5
    math = nodes.new('ShaderNodeMath')
    math.operation = 'GREATER_THAN'
    math.inputs[1].default_value = 0.5  # Threshold for glass

    # Create Output Node
    output = nodes.new('ShaderNodeOutputMaterial')

    # Link Nodes
    links.new(object_info.outputs['Object Index'], math.inputs[0])  # Object Index -> Math
    links.new(math.outputs['Value'], mix_shader.inputs['Fac'])      # Math -> Mix Shader Factor
    links.new(principled.outputs['BSDF'], mix_shader.inputs[1])     # Principled -> Mix Shader
    links.new(glass.outputs['BSDF'], mix_shader.inputs[2])          # Glass -> Mix Shader
    links.new(mix_shader.outputs['Shader'], output.inputs['Surface'])  # Mix Shader -> Output

    return mat



class MATERIAL_OT_OverrideToggle(bpy.types.Operator):
    bl_idname = "material.override_toggle"
    bl_label = "Toggle Material Override"
    bl_description = "Enable or disable Material Override in View Layer"

    def execute(self, context):
        view_layer = context.view_layer
        scene = context.scene

        if view_layer.material_override:
            # Store current material before disabling
            scene['stored_material_override'] = view_layer.material_override.name
            view_layer.material_override = None
            self.report({'INFO'}, "Material Override Disabled")
        else:
            # Try to retrieve or create material
            material = None
            material_name = scene.get('stored_material_override')
            
            if material_name:
                material = bpy.data.materials.get(material_name)
            
            # Create new material if none exists
            if not material:
                material = create_clay_material()
                scene['stored_material_override'] = material.name
                self.report({'INFO'}, "Created new Clay Override Material")
                
            view_layer.material_override = material
            self.report({'INFO'}, f"Material Override Enabled with '{material.name}'")
            
        return {'FINISHED'}

def draw_material_override_button(self, context):
    layout = self.layout
    view_layer = context.view_layer
    is_enabled = view_layer.material_override is not None

    # Insert the button to the right of the Overlays button
    row = layout.row(align=True)
    row.operator(
        "material.override_toggle",
        text="" if is_enabled else "",
        icon='MATERIAL' if is_enabled else 'META_DATA',
    )

@addon_updater_ops.make_annotations


class ClayModeAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    # Store API key in Blender's persistent preferences
    api_key: bpy.props.StringProperty(
        name="Gemini API Key",
        description="API Key for Gemini generative AI",
    )

    prompt_template: bpy.props.StringProperty(
        name="Prompt Template",
        description="Template for the AI-generated summaries. Use {names} to include object names.",
        default="Summarize the following object names into a short descriptive phrase:\n{names}"
    )
    

    # Updater preferences
    auto_check_update: bpy.props.BoolProperty(
        name="Auto-check for Update",
        description="If enabled, auto-check for updates using an interval",
        default=False
    ) 

    updater_interval_months: bpy.props.IntProperty(
        name="Months",
        description="Number of months between checking for updates",
        default=0,
        min=0
    )

    updater_interval_days: bpy.props.IntProperty(
        name="Days",
        description="Number of days between checking for updates",
        default=7,
        min=0,
        max=31
    )

    updater_interval_hours: bpy.props.IntProperty(
        name="Hours",
        description="Number of hours between checking for updates",
        default=0,
        min=0,
        max=23
    )

    updater_interval_minutes: bpy.props.IntProperty(
        name="Minutes",
        description="Number of minutes between checking for updates",
        default=0,
        min=0,
        max=59
    )

    def draw(self, context):
        layout = self.layout

        # Gemini API Key UI
        layout.label(text="Gemini API Settings")
        layout.prop(self, "api_key")

        layout.label(text="AI Prompt Template")
        layout.prop(self, "prompt_template", text="Prompt")


        # Updater Settings UI
        layout.label(text="Addon Updater Settings")
        addon_updater_ops.update_settings_ui(self, context)



class CLAY_OT_GroupWithSummary(bpy.types.Operator):
    bl_idname = "clay.group_with_summary"
    bl_label = "Group with AI Summary"
    bl_description = "Group selected objects with an AI-generated summarized name"

    def summarize_names(self, names):
        # Placeholder for AI summarization logic
        return "Group"

    def gather_all_objects(self, objs):
        all_objs = set(objs)
        for obj in objs:
            all_objs.update(self.gather_all_objects(obj.children))
        return all_objs

    def execute(self, context):
        selected_objs = context.selected_objects
        if not selected_objs:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}

        # Gather all selected objects and their descendants
        all_objs = self.gather_all_objects(selected_objs)

        # Calculate the combined bounding box
        inf = float('inf')
        min_corner = Vector((inf, inf, inf))
        max_corner = -min_corner
        for obj in all_objs:
            for corner in obj.bound_box:
                world_corner = obj.matrix_world @ Vector(corner)
                min_corner = Vector(map(min, min_corner, world_corner))
                max_corner = Vector(map(max, max_corner, world_corner))
        center = (min_corner + max_corner) / 2
        size = max_corner - min_corner

        # Create the bounding box (empty object)
        bpy.ops.object.empty_add(type='CUBE', location=center)
        bounding_box = context.object
        bounding_box.name = self.summarize_names([obj.name for obj in selected_objs])
        bounding_box.scale = size / 2

        # Parent only top-level selected objects to the bounding box
        for obj in selected_objs:
            obj.parent = bounding_box

        self.report({'INFO'}, f"Grouping done with name: {bounding_box.name}")
        return {'FINISHED'}


class CLAY_PT_GroupPanel(bpy.types.Panel):
    bl_label = "AI Grouping"
    bl_idname = "CLAY_PT_group_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'  # Creates a new "Tool" tab

    def draw(self, context):
        layout = self.layout
        layout.label(text="Group Objects with AI")
        layout.operator("clay.group_with_summary", text="Group with AI Summary")





def register():
    
    addon_updater_ops.register(bl_info)
    bpy.utils.register_class(ClayModeAddonPreferences)
    bpy.utils.register_class(MATERIAL_OT_OverrideToggle)
    bpy.utils.register_class(CLAY_OT_GroupWithSummary)
    bpy.types.VIEW3D_HT_header.append(draw_material_override_button)
    bpy.utils.register_class(CLAY_PT_GroupPanel)

def unregister():

    bpy.utils.unregister_class(CLAY_PT_GroupPanel)
    bpy.types.VIEW3D_HT_header.remove(draw_material_override_button)
    bpy.utils.unregister_class(CLAY_OT_GroupWithSummary)
    bpy.utils.unregister_class(MATERIAL_OT_OverrideToggle)
    bpy.utils.unregister_class(ClayModeAddonPreferences)
    addon_updater_ops.unregister()
    
    
    

if __name__ == "__main__":
    register()