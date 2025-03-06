from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf
import math

node = hou.pwd()
lopnode = hou.pwd().inputs()[0]
editable_stage = node.editableStage()
stage = lopnode.stage()

if not stage:
    raise ValueError("Invalid LOP node or USD stage not found.")

frame_list = []
frame = float(hou.intFrame())
time_code = Usd.TimeCode(frame)
motion_blur = True
camera_lop_selection = hou.LopSelectionRule(pattern=node.evalParm("camera")) # /cameras/camera1
camera_path = camera_lop_selection.expandedPaths(stage=stage)[0]
camera_prim = stage.GetPrimAtPath(camera_path)

if not camera_prim.IsValid():
    raise ValueError(f"Camera '{camera_path}' not found in USD stage.")
    
camera = UsdGeom.Camera(camera_prim)


# Check motion blur values
if motion_blur:
    shutter_open = camera.GetShutterOpenAttr().Get()
    shutter_close = camera.GetShutterCloseAttr().Get()
    frame_list.append(float(hou.intFrame())+shutter_open)
    frame_list.append(float(hou.intFrame()))
    frame_list.append(float(hou.intFrame())+shutter_close)
else:
    frame_list.append(float(hou.intFrame()))

   
# Get prim bounds
lop_selection = hou.LopSelectionRule(pattern=node.evalParm("prim")) # Use explicit paths to prims or wildcards(*) or collections
prims = lop_selection.expandedPaths(stage=stage)
bbox_coords = []

for f in frame_list:
    if prims != None:
        time_code = Usd.TimeCode(f)
        
        for prim in prims:
            prim_path = prim
            prim = stage.GetPrimAtPath(prim_path)
            
            if prim and prim.IsValid():
                    
                bbox_cache = UsdGeom.BBoxCache(time_code, [UsdGeom.Tokens.default_]) #, UsdGeom.Tokens.render], useExtentsHint=False, ignoreVisibility=False)
                bbox = bbox_cache.ComputeWorldBound(prim)
                bbox_min = bbox.ComputeAlignedRange().GetMin()
                bbox_max = bbox.ComputeAlignedRange().GetMax()
                
                bbox_0 = bbox_min
                bbox_1 = (bbox_min[0], bbox_min[1]+(bbox_max[1]-bbox_min[1]), bbox_min[2])
                bbox_2 = (bbox_min[0]+(bbox_max[0]-bbox_min[0]), bbox_min[1]+(bbox_max[1]-bbox_min[1]), bbox_min[2])
                bbox_3 = (bbox_min[0]+(bbox_max[0]-bbox_min[0]), bbox_min[1], bbox_min[2])
                bbox_4 = bbox_max
                bbox_5 = (bbox_max[0],bbox_max[1]-(bbox_max[1]-bbox_min[1]),bbox_max[2])
                bbox_6 = (bbox_max[0]-(bbox_max[0]-bbox_min[0]), bbox_max[1]-(bbox_max[1]-bbox_min[1]), bbox_max[2])
                bbox_7 = (bbox_max[0]-(bbox_max[0]-bbox_min[0]), bbox_max[1], bbox_max[2])
        
                bbox_coords_list = [bbox_0,bbox_1,bbox_2,bbox_3,bbox_4,bbox_5,bbox_6,bbox_7]
                
                for x in range(len(bbox_coords_list)):
                    bbox_coords.append(bbox_coords_list[x])
    
            
# Get ndc coords
def world_to_ndc(lop_node, camera_path, world_point):

    focal_length = camera.GetFocalLengthAttr().Get()
    horizontal_aperture = camera.GetHorizontalApertureAttr().Get()
    vertical_aperture = camera.GetVerticalApertureAttr().Get()
    near_clip, far_clip = camera.GetClippingRangeAttr().Get()
    camera_xform = UsdGeom.Xformable(camera_prim).ComputeLocalToWorldTransform(time_code)

    # Convert world space point to Gf.Vec3d
    world_pos = Gf.Vec3d(*world_point)

    # Convert world position to camera space (apply world-to-camera transform)
    view_matrix = camera_xform.GetInverse()
    cam_space_pos = view_matrix.Transform(world_pos)

    # Construct projection matrix
    aspect_ratio = horizontal_aperture / vertical_aperture
    fov_x = 2.0 * focal_length / horizontal_aperture
    fov_y = 2.0 * focal_length / vertical_aperture

    proj_matrix = Gf.Matrix4d(
        fov_x, 0, 0, 0,
        0, fov_y, 0, 0,
        0, 0, -(far_clip + near_clip) / (far_clip - near_clip), -2 * far_clip * near_clip / (far_clip - near_clip),
        0, 0, -1, 0
    )

    # Convert Vec3d to Vec4d (homogeneous coordinates for projection)
    cam_space_pos4 = Gf.Vec4d(cam_space_pos[0], cam_space_pos[1], cam_space_pos[2], 1.0)

    # Apply projection matrix
    clip_space_pos = proj_matrix * cam_space_pos4

    # Convert to NDC (divide by w)
    if clip_space_pos[3] != 0:
        ndc_x = (clip_space_pos[0] / clip_space_pos[3]) * 0.5 + 0.5
        ndc_y = (clip_space_pos[1] / clip_space_pos[3]) * 0.5 + 0.5
    else:
        raise ValueError("Invalid clip-space position (w=0), check input point.")

    return (ndc_x, ndc_y)
    

# Get Min and Max NDC values for X and Y coords
def get_min_max_ndc(bbox_coords):

    if len(bbox_coords) > 0:
        padding = 0.05
        ndc_x = []
        ndc_y = []
        for x in range(len(bbox_coords)):
            ndc_coords = world_to_ndc(lopnode, camera_path, bbox_coords[x])
            ndc_x.append(ndc_coords[0])
            ndc_y.append(ndc_coords[1])
        ndc_min_x = round(min(ndc_x)-padding,2)
        ndc_min_y = round(min(ndc_y)-padding,2)
        ndc_max_x = round(max(ndc_x)+padding,2)
        ndc_max_y = round(max(ndc_y)+padding,2)
        
        return (ndc_min_x, ndc_min_y, ndc_max_x, ndc_max_y)
        
# Set DataWindowNDC values on Render Settings
def set_dataWindowNDC():

    ndc_values = get_min_max_ndc(bbox_coords)
    
    if ndc_values != None:
        render_settings = editable_stage.GetPrimAtPath("/Render/rendersettings")
        dataWindowNDC_attr = render_settings.GetAttribute("dataWindowNDC")
        current_ndc_values = dataWindowNDC_attr.Get()
        
        min_x = current_ndc_values[0] if ndc_values[0] < current_ndc_values[0] else ndc_values[0]
        min_y = current_ndc_values[1] if ndc_values[1] < current_ndc_values[1] else ndc_values[1]
        max_x = current_ndc_values[2] if ndc_values[2] > current_ndc_values[2] else ndc_values[2]
        max_y = current_ndc_values[3] if ndc_values[3] > current_ndc_values[3] else ndc_values[3]
        
        dataWindowNDC_attr.Set((min_x,min_y,max_x,max_y))
        return (min_x,min_y,max_x,max_y)
        
        
set_dataWindowNDC()
