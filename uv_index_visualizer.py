bl_info = {
    "name": "Visualize UV indices of vertex/edge/face/loop in UV/Image View.",
    "author": "Tetii",
    "version": (1, 1),
    "blender": (2, 79, 0),
    "location": "Image Editor > Property Shelf > Visible UV Indecies",
    "description": "Drawing indecies at Image View",
    "warning": "",
    "support": "TESTING",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Image View"
}


import bpy
import bmesh
from bpy.props import BoolProperty, IntProperty, PointerProperty
from mathutils import Vector, Matrix
from math import pi
import blf
import bgl


class RenderUVIndex(bpy.types.Operator):

    bl_idname = "uv.render_uv_index"
    bl_label = "Render UV Index"
    bl_description = "Render UV Index"

    __handle = None
    
    @classmethod
    def __handle_add(cls, context):

        if cls.__handle is None:
            sie = bpy.types.SpaceImageEditor
            cls.__handle = sie.draw_handler_add(
                                            cls.__render, 
                                            (context,), 
                                            'WINDOW', 
                                            'POST_PIXEL'
                                        )


    @classmethod
    def __handle_remove(cls):

        if cls.__handle is not None:
            sie = bpy.types.SpaceImageEditor
            sie.draw_handler_remove(
                                    cls.__handle, 
                                    'WINDOW'
                                    )
            cls.__handle = None


    @classmethod
    def release_handle(cls):
        cls.__handle_remove()


    @classmethod
    def is_running(cls):
        return cls.__handle is not None


    @staticmethod
    def is_valid_context(context):

        obj = context.object

        if obj is None \
                or obj.type != 'MESH' \
                or context.object.mode != 'EDIT':
            return False
        
        for space in context.area.spaces:
            if space.type == 'IMAGE_EDITOR':
                break
        else:
            print("$"*5, "This line is unbelievable in is_valid_context", "$"*5)
            return False

        if space.image is not None \
                and space.image.type == 'RENDER_RESULT':
            return False
        
        return True


    @staticmethod
    def __render_text(size, v, s):
        
        blf.size(0, size, 72)
        blf.position(0, v.x, v.y, 0)
        blf.draw(0, s)


    @classmethod
    def __render(cls, context):

        if not cls.is_valid_context(context):
            return

        for region in context.area.regions:
            if region.type == 'WINDOW':
                break
        else:
            return

        scene = context.scene
        ruvi_props = scene.ruvi_properties
        uv_select_sync = scene.tool_settings.use_uv_select_sync
        black = (0.0, 0.0, 0.0, 1.0)
        quasi_black = (0.0, 0.0, 0.0, 0.3)
        blf.shadow(0, 3, 1.0, 0.0, 0.0, 1.0)
        blf.shadow_offset(0, 2, -2)

        [me, bm, uv_layer] = cls.__init_bmesh(context)

        for f in bm.faces:
            if not f.select and not uv_select_sync:
                continue

            selected_loops_count = 0
            uvc = Vector([0.0, 0.0]) #center uv of the face

            for loop1 in f.loops:

                uv1 = loop1[uv_layer].uv
                uvc += uv1 #loop1[uv_layer].uv
                if not loop1[uv_layer].select and not uv_select_sync:
                    continue
                selected_loops_count += 1

                # Draw Vert index
                if ruvi_props.verts:
                    if uv_select_sync and not loop1.vert.select:
                        continue
                    
                    cls.__render_text_index(
                                    context, 
                                    region, 
                                    loop1.vert.index, 
                                    uv1, 
                                    bg_color=quasi_black, 
                                    )

                # Get next loop parameter
                loop2, *arg = cls.__get_2nd_loop(loop1, uv_layer)
                if loop2 is None:
                    continue
                uv2, uvm, uvt, uvn = arg

                blf.enable(0, blf.ROTATION)

                # Draw Edge index
                if ruvi_props.edges:
                    if (not uv_select_sync and loop2[uv_layer].select) \
                            or (uv_select_sync and loop2.vert.select 
                                                and loop1.edge.select):

                        cls.__render_text_index(
                                        context, 
                                        region, 
                                        loop1.edge.index, 
                                        uvm, 
                                        uvt=uvt, 
                                        uvn=uvn,
                                        bg_color=quasi_black, 
                                        )

                blf.enable(0, blf.SHADOW)

                # Draw Loop index
                if ruvi_props.loops and not uv_select_sync:
                    
                    cls.__render_text_index(
                                    context, 
                                    region, 
                                    loop1.index, 
                                    uvm, 
                                    uvt=uvt, 
                                    uvn=uvn, 
                                    loop_offset=(1.0, 1.5),
                                    )

                blf.disable(0, blf.ROTATION)
                blf.disable(0, blf.SHADOW)

            # Draw Face index
            if ruvi_props.faces and (
                        (not uv_select_sync and selected_loops_count) or 
                        (uv_select_sync and f.select)
                    ):

                cls.__render_text_index(
                                context, 
                                region, 
                                f.index, 
                                uvc/len(f.loops), 
                                )
                
        
    def invoke(self, context, event):
        
        scene = context.scene

        if context.area.type == 'IMAGE_EDITOR':
            
            if not self.is_running():
                self.__handle_add(context)
            else:
                self.__handle_remove()

            # Redraw all UV/Image Editor Views
            for a in context.screen.areas:
                if a.type == context.area.type: # the filtering is necessary
                    a.tag_redraw()

            return {'FINISHED'}

        else:
            return {'CANCELLED'}


    @staticmethod
    def __get_2nd_loop(loop1, uv_layer):

        loop2 = loop1.link_loop_next

        if loop2 is None or loop1 == loop2:
            return None

        uv1 = loop1[uv_layer].uv
        uv2 = loop2[uv_layer].uv

        # middle vector between uv1 and uv2
        uvm = (uv1 + uv2) / 2.0
        # unit tangent vector from  uv1 to uv2
        uvt = uv2 - uv1
        if uvt.length != 0.0:
            uvt = uvt / uvt.length
        else:
            uvt.x, uvt.y = 1.0, 0.0
        # unit normal vector of uvt
        uvn = Vector([-uvt.y, uvt.x])

        return (loop2, uv2, uvm, uvt, uvn)


    @classmethod
    def __render_text_index(
                cls, 
                context, 
                region, 
                index, 
                uv,                     # uv vector to text position
                uvt=Vector([1.0, 0.0]), # tangent unit vector on uv
                uvn=Vector([0.0, 1.0]), # normal unit vector on uv
                loop_offset=(0.0, 0.0), # additional offset to loop text pos
                bg_color=None, 
                ):
        
        text = str(index)
        ruvi_props = scene = context.scene.ruvi_properties
        additional_offset = loop_offset[ruvi_props.edges]

        # Calcurate position and angle
        v = Vector(region.view2d.view_to_region(uv.x, uv.y))
        text_w, text_h = blf.dimensions(0, text)

        offset = (text_w * uvt + text_h * uvn) / 2
        sub_offset = additional_offset * text_h * uvn

        vxo = Vector([1, 0])
        vxy = Vector([1,-1])
        angle = uvt.angle_signed(vxo)
        if uvt.angle_signed(vxy) > 0:
            v = v - offset + sub_offset
        else:
            v = v + offset + sub_offset
            angle -= pi

        blf.rotation(0, angle)

        # Render index
        if bg_color is not None:
            cls.__draw_background(bg_color, text, v, angle)
        font_size = ruvi_props.font_size
        cls.__render_text(font_size, v, text)


    @staticmethod
    def __draw_background(color, text, vo, angle=0.0):

        text_w, text_h = blf.dimensions(0, text)
        font_w = text_w / len(text)

        a = 0.6
        x1 = vo.x  - font_w / 2
        y1 = vo.y  - text_h / 2 * a
        x2 = x1 + text_w + font_w
        y2 = y1 + text_h * (1 + a)

        poss = [
                Vector([x1, y1]),
                Vector([x1, y2]),
                Vector([x2, y2]),
                Vector([x2, y1])
            ]

        if angle != 0.0:
            rot = Matrix.Rotation(angle, 2, 'Z')
            for i in range(len(poss)):
                poss[i] = rot * (poss[i] - vo) + vo

        # render box
        bgl.glEnable(bgl.GL_BLEND)
        bgl.glBegin(bgl.GL_QUADS)
        bgl.glColor4f(*color)
        for v in poss:
            bgl.glVertex2f(v.x, v.y)
        bgl.glEnd()
        bgl.glColor4f(1.0, 1.0, 1.0, 1.0)


    @staticmethod
    def __init_bmesh(context):

        me = context.active_object.data
        bm = bmesh.from_edit_mesh(me)
        uv_layer = bm.loops.layers.uv.verify()
        bm.faces.layers.tex.verify()  # currently blender needs both layers.
        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        
        return (me, bm, uv_layer)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

class IMAGE_PT_RUVI(bpy.types.Panel):

    bl_label = "Visible UV Indecies"
    bl_space_type = "IMAGE_EDITOR"
    bl_region_type = "UI"


    def draw(self, context):

        scene = context.scene
        ruvi_props = scene.ruvi_properties
        layout = self.layout
        
        if not RenderUVIndex.is_running():
            layout.operator(RenderUVIndex.bl_idname, text="Start", icon="PLAY")
        else:
            layout.operator(RenderUVIndex.bl_idname, text="Stop", icon="PAUSE")

        layout.prop(ruvi_props, "faces")
        layout.prop(ruvi_props, "verts")
        layout.prop(ruvi_props, "edges")

        split = layout.split() # for gray out by use_uv_select_sync
        split.active = not scene.tool_settings.use_uv_select_sync
        split.prop(ruvi_props, "loops")

        layout.prop(ruvi_props, "font_size")
        

    @classmethod
    def poll(cls, context):

        return bpy.types.UV_OT_render_uv_index.is_valid_context(context)


class RenderUVIndexProperties(bpy.types.PropertyGroup):

    loops = BoolProperty(
        name = "Loops", 
        default = False
        )

    faces = BoolProperty(
        name = "Faces", 
        default = False
        )

    verts = BoolProperty(
        name = "Verts", 
        default = False
        )

    edges = BoolProperty(
        name = "Edges", 
        default = False
        )

    font_size = IntProperty(
        name="Text Size",
        description="Text size",
        default=11,
        min=8,
        max=32
        )


def init_props():

    scene = bpy.types.Scene
    scene.ruvi_properties = bpy.props.PointerProperty(
                                        type=RenderUVIndexProperties
                                    )


def clear_props():

    scene = bpy.types.Scene
    del scene.ruvi_properties


# Using addon_keymaps[], exeption error is thrown as follow
# RuntimeError: Error: KeyMapItem 'FILE_OT_select' cannot be removed from 'View3D Dolly Modal'
def remove_keymap_item(keyconfigs_key, keymap_name, keymap_item_name):
    
    wm = bpy.context.window_manager
    kc = wm.keyconfigs[keyconfigs_key]
    
    km = kc.keymaps.get(keymap_name)
    if km is None:
        return False
    
    for kmi in km.keymap_items:
        if kmi.idname == keymap_item_name:
            km.keymap_items.remove(kmi)
            return True
    else:
        return False
    

def register():
    
    bpy.utils.register_module(__name__)
    init_props()

    wm = bpy.context.window_manager
    kc = wm.keyconfigs["Blender Addon"]
    
    # If space_type is 'IMAGE_EDITOR', short cut key does not work. 
    km = kc.keymaps.new(name="UV Editor", space_type='EMPTY')
    kmi = km.keymap_items.new(
                        RenderUVIndex.bl_idname, 
                        'I', 
                        'PRESS', 
                        ctrl=True, 
                        alt=True
                    )
    

def unregister():

    # Remove handle before unregisting classes
    bpy.types.UV_OT_render_uv_index.release_handle()
    
    bpy.utils.unregister_module(__name__)
    clear_props()
    
    remove_keymap_item(
                    keyconfigs_key="Blender Addon", 
                    keymap_name="UV Editor", 
                    keymap_item_name=RenderUVIndex.bl_idname
                )
 

if __name__ == "__main__":
    
    try:
        unregister()
    except:
        pass
    
    register()
