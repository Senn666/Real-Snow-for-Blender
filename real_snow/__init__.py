# SPDX-License-Identifier: GPL-2.0-or-later

bl_info = {
    "name": "Real Snow",
    "description": "Generate snow mesh - compatible with Blender 5.3",
    "author": "Marco Pavanello, Drew Perttula",
    "version": (5, 3, 0),
    "blender": (4, 2, 0),
    "location": "View 3D > Properties Panel",
    "doc_url": "{BLENDER_MANUAL_URL}/addons/object/real_snow.html",
    "tracker_url": "https://gitlab.com/marcopavanello/real-snow/-/issues",
    "support": "COMMUNITY",
    "category": "Object",
    }


# Libraries
import math
import os
import random
import time

import bpy
import bmesh
from bpy.props import BoolProperty, FloatProperty, IntProperty, PointerProperty
from bpy.types import Operator, Panel, PropertyGroup
from mathutils import Vector


# Panel
class REAL_PT_snow(Panel):
    bl_space_type = "VIEW_3D"
    bl_context = "objectmode"
    bl_region_type = "UI"
    bl_label = "Snow"
    bl_category = "Real Snow"

    def draw(self, context):
        scn = context.scene
        settings = scn.snow
        layout = self.layout

        col = layout.column(align=True)
        col.prop(settings, 'coverage', slider=True)
        col.prop(settings, 'height')

        layout.use_property_split = True
        layout.use_property_decorate = False
        flow = layout.grid_flow(row_major=True, columns=0, even_columns=False, even_rows=False, align=True)
        col = flow.column()
        col.prop(settings, 'vertices')

        row = layout.row(align=True)
        row.scale_y = 1.5
        row.operator("snow.create", text="Add Snow", icon="FREEZE")


class SNOW_OT_Create(Operator):
    bl_idname = "snow.create"
    bl_label = "Create Snow"
    bl_description = "Create snow"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context) -> bool:
        return bool(context.selected_objects)

    def execute(self, context):
        coverage = context.scene.snow.coverage
        height = context.scene.snow.height
        vertices = context.scene.snow.vertices

        # Get a list of selected objects, except non-mesh objects
        input_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
        snow_list = []
        # Start UI progress bar
        length = len(input_objects)
        context.window_manager.progress_begin(0, 10)
        timer = 0
        for obj in input_objects:
            # Timer
            context.window_manager.progress_update(timer)
            # Duplicate mesh
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            context.view_layer.objects.active = obj
            object_eval = obj.evaluated_get(context.view_layer.depsgraph)
            mesh_eval = bpy.data.meshes.new_from_object(object_eval)
            snow_object = bpy.data.objects.new("Snow", mesh_eval)
            snow_object.matrix_world = obj.matrix_world
            context.collection.objects.link(snow_object)
            bpy.ops.object.select_all(action='DESELECT')
            context.view_layer.objects.active = snow_object
            snow_object.select_set(True)
            bpy.ops.object.mode_set(mode = 'EDIT')
            bm_orig = bmesh.from_edit_mesh(snow_object.data)
            bm_copy = bm_orig.copy()
            bm_copy.transform(obj.matrix_world)
            bm_copy.normal_update()
            # Get faces data
            delete_faces(vertices, bm_copy, snow_object)
            ballobj = add_metaballs(context, height, snow_object)
            context.view_layer.objects.active = snow_object
            surface_area = area(snow_object)
            snow = add_particles(context, surface_area, height, coverage, snow_object, ballobj)
            add_modifiers(snow)
            # Place inside collection
            context.view_layer.active_layer_collection = context.view_layer.layer_collection
            if "Snow" not in context.scene.collection.children:
                coll = bpy.data.collections.new("Snow")
                context.scene.collection.children.link(coll)
            else:
                coll = bpy.data.collections["Snow"]
            coll.objects.link(snow)
            context.view_layer.layer_collection.collection.objects.unlink(snow)
            add_material(snow)
            # Parent with object
            snow.parent = obj
            snow.matrix_parent_inverse = obj.matrix_world.inverted()
            # Add snow to list
            snow_list.append(snow)
            # Update progress bar
            timer += 0.1 / length
        # Select created snow meshes
        for s in snow_list:
            s.select_set(True)
        # End progress bar
        context.window_manager.progress_end()

        return {'FINISHED'}


def add_modifiers(snow):
    bpy.ops.object.transform_apply(location=False, scale=True, rotation=False)
    # Decimate the mesh to get rid of some visual artifacts
    snow.modifiers.new("Decimate", 'DECIMATE')
    snow.modifiers["Decimate"].ratio = 0.5
    snow.modifiers.new("Subdiv", "SUBSURF")
    snow.modifiers["Subdiv"].render_levels = 1
    snow.modifiers["Subdiv"].quality = 1
    # Blender 4.2+ removed Object.cycles.use_adaptive_subdivision.
    # Adaptive subdivision is now configured in the Cycles render settings;
    # skip it here so the add-on keeps working on modern versions.
    if hasattr(snow, "cycles") and hasattr(snow.cycles, "use_adaptive_subdivision"):
        snow.cycles.use_adaptive_subdivision = True


def add_particles(context, surface_area: float, height: float, coverage: float, snow_object: bpy.types.Object, ballobj: bpy.types.Object):
    # Approximate the number of particles to be emitted
    number = int(surface_area * 50 * (height ** -2) * ((coverage / 100) ** 2))
    bpy.ops.object.particle_system_add()
    particles = snow_object.particle_systems[0]
    psettings = particles.settings
    psettings.type = 'HAIR'
    psettings.render_type = 'OBJECT'
    # Generate random number for seed
    random_seed = random.randint(0, 1000)
    particles.seed = random_seed
    # Set particles object
    psettings.particle_size = height
    psettings.instance_object = ballobj
    psettings.count = number
    # Convert particles to mesh
    bpy.ops.object.select_all(action='DESELECT')
    context.view_layer.objects.active = ballobj
    ballobj.select_set(True)
    bpy.ops.object.convert(target='MESH')
    snow = bpy.context.active_object
    snow.scale = [0.09, 0.09, 0.09]
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY')
    bpy.ops.object.select_all(action='DESELECT')
    snow_object.select_set(True)
    bpy.ops.object.delete()
    snow.select_set(True)
    return snow


def add_metaballs(context, height: float, snow_object: bpy.types.Object) -> bpy.types.Object:
    ball_name = "SnowBall"
    ball = bpy.data.metaballs.new(ball_name)
    ballobj = bpy.data.objects.new(ball_name, ball)
    bpy.context.scene.collection.objects.link(ballobj)
    # These settings have proven to work on a large amount of scenarios
    ball.resolution = 0.7 * height + 0.3
    ball.threshold = 1.3
    element = ball.elements.new()
    element.radius = 1.5
    element.stiffness = 0.75
    ballobj.scale = [0.09, 0.09, 0.09]
    return ballobj


def delete_faces(vertices, bm_copy, snow_object: bpy.types.Object):
    # Find upper faces
    if vertices:
        selected_faces = set(face.index for face in bm_copy.faces if face.select)
    # Based on a certain angle, find all faces not pointing up
    down_faces = set(face.index for face in bm_copy.faces if Vector((0, 0, -1.0)).angle(face.normal, 4.0) < (math.pi / 2.0 + 0.5))
    bm_copy.free()
    bpy.ops.mesh.select_all(action='DESELECT')
    # Select upper faces
    mesh = bmesh.from_edit_mesh(snow_object.data)
    for face in mesh.faces:
        if vertices:
            if face.index not in selected_faces:
                face.select = True
        if face.index in down_faces:
            face.select = True
    # Delete unnecessary faces
    faces_select = [face for face in mesh.faces if face.select]
    bmesh.ops.delete(mesh, geom=faces_select, context='FACES_KEEP_BOUNDARY')
    mesh.free()
    bpy.ops.object.mode_set(mode = 'OBJECT')


def area(obj: bpy.types.Object) -> float:
    bm_obj = bmesh.new()
    bm_obj.from_mesh(obj.data)
    bm_obj.transform(obj.matrix_world)
    area = sum(face.calc_area() for face in bm_obj.faces)
    bm_obj.free()
    return area


def add_material(obj: bpy.types.Object):
    mat_name = "Snow"
    # If material doesn't exist, create it
    if mat_name in bpy.data.materials:
        bpy.data.materials[mat_name].name = mat_name+".001"
    mat = bpy.data.materials.new(mat_name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    # Delete all nodes
    for node in nodes:
        nodes.remove(node)
    # Add nodes
    output = nodes.new('ShaderNodeOutputMaterial')
    principled = nodes.new('ShaderNodeBsdfPrincipled')
    vec_math = nodes.new('ShaderNodeVectorMath')
    com_xyz = nodes.new('ShaderNodeCombineXYZ')
    dis = nodes.new('ShaderNodeDisplacement')
    mul1 = nodes.new('ShaderNodeMath')
    add1 = nodes.new('ShaderNodeMath')
    add2 = nodes.new('ShaderNodeMath')
    mul2 = nodes.new('ShaderNodeMath')
    mul3 = nodes.new('ShaderNodeMath')
    range1 = nodes.new('ShaderNodeMapRange')
    range2 = nodes.new('ShaderNodeMapRange')
    range3 = nodes.new('ShaderNodeMapRange')
    vor = nodes.new('ShaderNodeTexVoronoi')
    noise1 = nodes.new('ShaderNodeTexNoise')
    noise2 = nodes.new('ShaderNodeTexNoise')
    noise3 = nodes.new('ShaderNodeTexNoise')
    mapping = nodes.new('ShaderNodeMapping')
    coord = nodes.new('ShaderNodeTexCoord')
    # Change location
    output.location = (100, 0)
    principled.location = (-200, 600)
    vec_math.location = (-400, 400)
    com_xyz.location = (-600, 400)
    dis.location = (-200, -100)
    mul1.location = (-400, -100)
    add1.location = (-600, -100)
    add2.location = (-800, -100)
    mul2.location = (-1000, -100)
    mul3.location = (-1000, -300)
    range1.location = (-400, 200)
    range2.location = (-1200, -300)
    range3.location = (-800, -300)
    vor.location = (-1500, 200)
    noise1.location = (-1500, 0)
    noise2.location = (-1500, -250)
    noise3.location = (-1500, -500)
    mapping.location = (-1700, 0)
    coord.location = (-1900, 0)
    # Change node parameters
    # NOTE: Blender 4.1+ renamed and re-ordered the Principled BSDF sockets.
    # Access them BY NAME so future versions don't silently shift indices.
    def setval(node, sock_name, value):
        sock = node.inputs.get(sock_name)
        if sock is not None:
            try:
                sock.default_value = value
            except (TypeError, ValueError):
                pass

    principled.distribution = "MULTI_GGX"
    principled.subsurface_method = "RANDOM_WALK_SKIN"
    setval(principled, "Base Color", (0.904, 0.904, 0.904, 1.0))
    setval(principled, "Subsurface Weight", 1.0)     # was inputs[7]
    setval(principled, "Subsurface Scale", 1.0)      # was inputs[9]
    setval(principled, "Subsurface Radius", (0.36, 0.46, 0.6))  # was inputs[8]
    setval(principled, "Specular IOR Level", 0.224)  # was inputs[12] (Specular)
    setval(principled, "Roughness", 0.1)             # was inputs[2]
    setval(principled, "Coat Roughness", 0.1)        # was inputs[19]
    setval(principled, "Coat IOR", 1.2)              # was inputs[20]
    vec_math.operation = "MULTIPLY"
    vec_math.inputs[1].default_value[0] = 0.5
    vec_math.inputs[1].default_value[1] = 0.5
    vec_math.inputs[1].default_value[2] = 0.5
    com_xyz.inputs[0].default_value = 0.36
    com_xyz.inputs[1].default_value = 0.46
    com_xyz.inputs[2].default_value = 0.6
    dis.inputs[1].default_value = 0.1
    dis.inputs[2].default_value = 0.3
    mul1.operation = "MULTIPLY"
    mul1.inputs[1].default_value = 0.1
    mul2.operation = "MULTIPLY"
    mul2.inputs[1].default_value = 0.6
    mul3.operation = "MULTIPLY"
    mul3.inputs[1].default_value = 0.4
    range1.inputs[1].default_value = 0.525
    range1.inputs[2].default_value = 0.58
    range2.inputs[1].default_value = 0.069
    range2.inputs[2].default_value = 0.757
    range3.inputs[1].default_value = 0.069
    range3.inputs[2].default_value = 0.757
    vor.feature = "N_SPHERE_RADIUS"
    vor.inputs[2].default_value = 30
    noise1.inputs[2].default_value = 12
    noise2.inputs[2].default_value = 2
    noise2.inputs[3].default_value = 4
    noise3.inputs[2].default_value = 1
    noise3.inputs[3].default_value = 4
    mapping.inputs[3].default_value[0] = 12
    mapping.inputs[3].default_value[1] = 12
    mapping.inputs[3].default_value[2] = 12
    # Link nodes
    link = mat.node_tree.links

    def find_sock(collection, key):
        # Blender 4.x/5.x renamed sockets; multiple sockets may share a name
        # (e.g. Math has three "Value" inputs), so fall back to identifier.
        s = collection.get(key)
        if s is not None:
            return s
        for s in collection:
            if s.identifier == key:
                return s
        return None

    def connect(from_node, from_sock, to_node, to_sock):
        """Link by socket name or identifier (indices shifted in 4.x/5.x)."""
        src = find_sock(from_node.outputs, from_sock)
        dst = find_sock(to_node.inputs, to_sock)
        if src is not None and dst is not None:
            link.new(src, dst)

    connect(principled, "BSDF", output, "Surface")
    connect(vec_math, "Vector", principled, "Subsurface Radius")
    connect(com_xyz, "Vector", vec_math, "Vector")
    connect(dis, "Displacement", output, "Displacement")
    connect(mul1, "Value", dis, "Height")
    connect(add1, "Value", mul1, "Value")
    connect(add2, "Value", add1, "Value")
    connect(mul2, "Value", add2, "Value")
    connect(mul3, "Value", add2, "Value_001")
    connect(range1, "Result", principled, "Coat Weight")
    connect(range2, "Result", mul3, "Value")
    connect(range3, "Result", add1, "Value_001")
    connect(vor, "Radius", range1, "Value")
    connect(noise1, "Fac", mul2, "Value")
    connect(noise2, "Fac", range2, "Value")
    connect(noise3, "Fac", range3, "Value")
    connect(mapping, "Vector", vor, "Vector")
    connect(mapping, "Vector", noise1, "Vector")
    connect(mapping, "Vector", noise2, "Vector")
    connect(mapping, "Vector", noise3, "Vector")
    connect(coord, "Object", mapping, "Vector")

    # Set displacement and add material (5.x moved this off mat.cycles)
    if hasattr(mat, "displacement_method"):
        mat.displacement_method = "DISPLACEMENT"
    else:
        setval(mat, "displacement_method", "DISPLACEMENT")
    obj.data.materials.append(mat)


# Properties
class SnowSettings(PropertyGroup):
    coverage : IntProperty(
        name = "Coverage",
        description = "Percentage of the object to be covered with snow",
        default = 100,
        min = 0,
        max = 100,
        subtype = 'PERCENTAGE'
        )

    height : FloatProperty(
        name = "Height",
        description = "Height of the snow",
        default = 0.3,
        step = 1,
        precision = 2,
        min = 0.1,
        max = 1
        )

    vertices : BoolProperty(
        name = "Selected Faces",
        description = "Add snow only on selected faces",
        default = False
        )


#############################################################################################
classes = (
    REAL_PT_snow,
    SNOW_OT_Create,
    SnowSettings
    )

register, unregister = bpy.utils.register_classes_factory(classes)

# Register
def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.snow = PointerProperty(type=SnowSettings)


# Unregister
def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.snow


if __name__ == "__main__":
    register()
