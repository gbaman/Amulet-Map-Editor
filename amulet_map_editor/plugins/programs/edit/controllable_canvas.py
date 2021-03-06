from typing import TYPE_CHECKING
import wx

from .canvas import EditCanvas
from amulet_map_editor.opengl.mesh.world_renderer.world import sin, cos

if TYPE_CHECKING:
    from amulet.api.world import World
    from .edit import EditExtension


key_map = {
    'up': wx.WXK_SPACE,
    'down': wx.WXK_SHIFT,
    'forwards': 87,
    'backwards': 83,
    'left': 65,
    'right': 68,

    'look_left': 74,
    'look_right': 76,
    'look_up': 73,
    'look_down': 75,
}


class ControllableEditCanvas(EditCanvas):
    def __init__(self, world_panel: 'EditExtension', world: 'World'):
        super().__init__(world_panel, world)
        self._last_mouse_x = 0
        self._last_mouse_y = 0
        self._mouse_delta_x = 0
        self._mouse_delta_y = 0
        self._mouse_lock = False
        self.Bind(wx.EVT_MIDDLE_UP, self._toggle_mouse_lock)
        self.Bind(wx.EVT_LEFT_UP, self._box_click)
        self.Bind(wx.EVT_RIGHT_UP, self._toggle_selection_mode)
        self.Bind(wx.EVT_MOTION, self._on_mouse_motion)

        self.Bind(wx.EVT_KEY_DOWN, self._on_key_press)
        self.Bind(wx.EVT_KEY_UP, self._on_key_release)
        self.Bind(wx.EVT_MOUSEWHEEL, self._mouse_wheel)
        self.Bind(wx.EVT_KILL_FOCUS, self._on_loss_focus)

    def _mouse_wheel(self, evt):
        self._camera_move_speed += 0.2 * evt.GetWheelRotation() / evt.GetWheelDelta()
        if self._camera_move_speed < 0.1:
            self._camera_move_speed = 0.1
        evt.Skip()

    def _toggle_mouse_lock(self, evt):
        self.SetFocus()
        if self._mouse_lock:
            self._release_mouse()
        else:
            self.CaptureMouse()
            wx.SetCursor(wx.Cursor(wx.CURSOR_BLANK))
            self._last_mouse_x, self._last_mouse_y = evt.GetPosition()
            self._mouse_lock = True

    def _process_inputs(self, evt):
        forward, up, right, pitch, yaw = 0, 0, 0, 0, 0
        if key_map['up'] in self._keys_pressed:
            up += 1
        if key_map['down'] in self._keys_pressed:
            up -= 1
        if key_map['forwards'] in self._keys_pressed:
            forward += 1
        if key_map['backwards'] in self._keys_pressed:
            forward -= 1
        if key_map['left'] in self._keys_pressed:
            right -= 1
        if key_map['right'] in self._keys_pressed:
            right += 1

        if self._mouse_lock:
            pitch = self._mouse_delta_y * 0.07
            yaw = self._mouse_delta_x * 0.07
        else:
            pitch = 0
            yaw = 0
        self._mouse_delta_x = 0
        self._mouse_delta_y = 0
        self.move_camera_relative(forward, up, right, pitch, yaw)
        evt.Skip()

    def move_camera_relative(self, forward, up, right, pitch, yaw):
        if (forward, up, right, pitch, yaw) == (0, 0, 0, 0, 0):
            return
        self._camera[0] += self._camera_move_speed * (cos(self._camera[4]) * right + sin(self._camera[4]) * forward)
        self._camera[1] += self._camera_move_speed * up
        self._camera[2] += self._camera_move_speed * (sin(self._camera[4]) * right - cos(self._camera[4]) * forward)

        self._camera[3] += self._camera_rotate_speed * pitch
        if not -90 <= self._camera[3] <= 90:
            self._camera[3] = max(min(self._camera[3], 90), -90)
        self._camera[4] += self._camera_rotate_speed * yaw
        self._collision_locations_cache = None
        self._transformation_matrix = None
        self._render_world.camera = self._camera
        self._change_box_location()

    def _change_box_location(self):
        if self._select_style:
            location = self._collision_location_closest()
        else:
            location = self._collision_location_distance(10)
        if self._selection_box.select_state == 0:
            self._selection_box.point1 = self._selection_box.point2 = location
            self._selection_box.point2 += 1
            self._selection_box.create_geometry()
        elif self._selection_box.select_state == 1:
            self._selection_box.point2 = location + 1
            self._selection_box.create_geometry()
        elif self._selection_box.select_state == 2:
            self._selection_box2.point1 = self._selection_box2.point2 = location
            self._selection_box2.point2 += 1
            self._selection_box2.create_geometry()

    def box_select(self):
        if self._selection_box.select_state <= 1:
            self._selection_box.select_state += 1
            self._selection_box.create_geometry()
        elif self._selection_box.select_state == 2:
            self._selection_box.point1, self._selection_box.point2 = self._selection_box2.point1, self._selection_box2.point2
            self._selection_box.create_geometry()
            self._selection_box.select_state = 1

    def _box_click(self, evt):
        self.box_select()
        evt.Skip()

    def _toggle_selection_mode(self, evt):
        self._select_style = not self._select_style
        self._change_box_location()
        evt.Skip()

    def _release_mouse(self):
        wx.SetCursor(wx.NullCursor)
        try:
            self.ReleaseMouse()
        except:
            pass
        self._mouse_lock = False

    def _on_mouse_motion(self, evt):
        if self._mouse_lock:
            mouse_x, mouse_y = evt.GetPosition()
            dx = mouse_x - self._last_mouse_x
            dy = mouse_y - self._last_mouse_y
            self._last_mouse_x, self._last_mouse_y = (
                int(self.GetSize()[0] / 2),
                int(self.GetSize()[1] / 2),
            )
            # only if location actually changed from the center, because WarpPointer may generate a mouse motion event
            # this check avoids using WarpPointer for events caused by WarpPointer
            if dx != 0 or dy != 0:
                self.WarpPointer(self._last_mouse_x, self._last_mouse_y)
            self._mouse_delta_x += dx
            self._mouse_delta_y += dy

    def _on_key_release(self, event):
        key = event.GetUnicodeKey()
        if key == wx.WXK_NONE:
            key = event.GetKeyCode()
        if key in self._keys_pressed:
            self._keys_pressed.remove(key)

    def _on_key_press(self, event):
        key = event.GetUnicodeKey()
        if key == wx.WXK_NONE:
            key = event.GetKeyCode()
        self._keys_pressed.add(key)
        if key == wx.WXK_ESCAPE:
            self._escape()

    def _on_loss_focus(self, evt):
        self._escape()
        evt.Skip()

    def _escape(self):
        self._keys_pressed.clear()
        self._release_mouse()