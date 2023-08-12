import numpy as np
import cv2 as cv
import time
import copy


from utils import set_marker_reference_coords, resize_for_laptop, get_base_center_voxels
from background_foreground_segmentation import apply_segmentation
from board import Board


parameters = {
	'obj01.mp4': {'circle_mask_size': 15, 'window_size': (10, 10), 'undist_axis': 55},
	#'obj02.mp4': {'circle_mask_size': 13, 'window_size': (9, 9), 'undist_axis': 60},
	#'obj03.mp4': {'circle_mask_size': 13, 'window_size': (9, 9), 'undist_axis': 70},
	#'obj04.mp4': {'circle_mask_size': 15, 'window_size': (10, 10), 'undist_axis': 55},
}


using_laptop = False
#voxel_cube_dim = 2 # set by default



def main():
	 
	# Set the marker reference coordinates for the 24 polygonls
	marker_reference = set_marker_reference_coords()
 
	camera_matrix = np.load('./calibration_info/cameraMatrix.npy')
	dist = np.load('./calibration_info/dist.npy')
 
	axis_centroid = np.float32([[20,0,0], [0,20,0], [0,0,30]]).reshape(-1,3)
	 
	# Iterate for each object
	for obj, hyper_param in parameters.items():
	  
		print(f'Marker Detector for {obj}...')
		input_video = cv.VideoCapture(f"../data/{obj}")
		  
		# Get video properties
		frame_width = int(input_video.get(cv.CAP_PROP_FRAME_WIDTH))
		frame_height = int(input_video.get(cv.CAP_PROP_FRAME_HEIGHT))

		actual_fps = 0
		avg_fps = 0.0
		obj_id = obj.split('.')[0]

		undistorted_resolution = None
		prev_frameg = None
  
		unidst_axis = hyper_param['undist_axis']
  
		axis_vertical_edges = np.float32([
											[-unidst_axis, -unidst_axis, 70], [-unidst_axis, unidst_axis, 70],
											[unidst_axis ,unidst_axis, 70], [unidst_axis, -unidst_axis, 70],
											[-unidst_axis, -unidst_axis, 70 + unidst_axis * 2],[-unidst_axis, unidst_axis, 70 + unidst_axis * 2],
											[unidst_axis, unidst_axis, 70 + unidst_axis * 2],[unidst_axis, -unidst_axis, 70 + unidst_axis * 2]
										])


		# Get the coordinates of the voxel center
		base_center_voxels = get_base_center_voxels(unidst_axis)

		# Initialize an index array to mark the mantained voxel that will determine the object volume
		V_set = np.ones((np.power(unidst_axis, 3), 1), dtype=np.int32)

		# create the board object
		board = Board(n_polygons=24, circle_mask_size=hyper_param['circle_mask_size'])
  
		# Create output video writer initialized at None since we do not know the undistorted resolution
		output_video = None
  

		while True:
			print(f'------------------------------ {actual_fps} ------------------------------')
			start = time.time()
			   
			# Extract a frame
			ret, frame = input_video.read()

			if not ret:	break
   
   
			# Apply the segmentation
			resulting_mask, segmented_frame = apply_segmentation(obj, frame)

		   
			frameg = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
			_, thresh = cv.threshold(frameg, 0, 255, cv.THRESH_BINARY + cv.THRESH_OTSU)
			mask = np.zeros_like(frameg)
   
			   
			if(actual_fps % 10 == 0): 
				# Each 10 frames recompute the whole features to track
				board.find_interesting_points(thresh, frameg, mask)
			else: 
				# The other frame use the Lucaks Kanade Optical Flow to estimate the postition of the traked features based on the previous frame
				board.apply_LF_OF(thresh, prev_frameg, frameg, mask, hyper_param['window_size'])
	 
			   
			#reshaped_clockwise = board.get_clockwise_vertices_initial()
			reshaped_clockwise = board.polygons_check_and_clockwise()
   
			# Obtain the dictionary of statistics
			pixsl_info = board.compute_markers(thresh, reshaped_clockwise, marker_reference)

			# Draw the marker detector stuff
			edited_frame = board.draw_stuff(frame)
   
   
			if pixsl_info.shape[0] >= 6:
       
				twoD_points = pixsl_info[:,1:3]
				threeD_points = pixsl_info[:,3:6]
    

				# Find the rotation and translation vectors
				ret, rvecs, tvecs = cv.solvePnP(objectPoints=threeD_points.astype('float32'), imagePoints=twoD_points.astype('float32'), cameraMatrix=camera_matrix, distCoeffs=dist, flags=cv.SOLVEPNP_IPPE)

				# Computing the Camera Projection Matrix
				rot_matx, _ = cv.Rodrigues(rvecs)
				rot_tran_mtx = np.concatenate([rot_matx, tvecs], axis=-1)
				proj_mtx = np.matmul(camera_matrix, rot_tran_mtx)

				# Homogeneous coordinates
				voxels_cube_centres_exp = np.concatenate((base_center_voxels, np.ones((*base_center_voxels.shape[:-1], 1))), axis=-1)

				# Get the prjection of the voxels center into the image
				proj_voxels = np.transpose(np.matmul(proj_mtx, np.reshape(np.transpose(voxels_cube_centres_exp), (4, np.power(unidst_axis, 3)))))
    
	 
				imgpts_centroid, _ = cv.projectPoints(objectPoints=axis_centroid, rvec=rvecs, tvec=tvecs, cameraMatrix=camera_matrix, distCoeffs=dist)
				imgpts_cube, _ = cv.projectPoints(objectPoints=axis_vertical_edges, rvec=rvecs, tvec=tvecs, cameraMatrix=camera_matrix, distCoeffs=dist)
			   		  	 
		  
				newCameraMatrix, roi = cv.getOptimalNewCameraMatrix(camera_matrix, dist, (frame_width, frame_height), 1, (frame_width, frame_height))
		  
				# Undistort the image
				undist = cv.undistort(edited_frame, camera_matrix, dist, None, newCameraMatrix)	
				x, y, w, h = roi
				undist = undist[y:y+h, x:x+w] # Adjust the image resolution

				

				# Update the undistorted_resolution and output_video the first time that the undistorted image resutn a valid shape
				if undistorted_resolution is None: 
					undistorted_resolution = undist.shape[:2]
					output_video = cv.VideoWriter(f'../output_project/{obj_id}.mp4', cv.VideoWriter_fourcc(*'mp4v'), input_video.get(cv.CAP_PROP_FPS), np.flip(undistorted_resolution))
    
    
				undist = board.draw_origin(undist, (board.centroid[0], undistorted_resolution[0] // 2), np.int32(imgpts_centroid))
				undist = board.draw_cube(undist, np.int32(imgpts_cube))
    
    
				# Undistorting the segmented frame to analyze the voxels centre
				undist_b_f_image = cv.undistort(resulting_mask, camera_matrix, dist, None, newCameraMatrix)	

				for idx, voxel_coords in enumerate(proj_voxels):
					print(int(voxel_coords[0] / voxel_coords[2]), int(voxel_coords[1] / voxel_coords[2]), undist_b_f_image[int(voxel_coords[0] / voxel_coords[2]), int(voxel_coords[1] / voxel_coords[2])])
					#cv.drawMarker(undist, (int(voxel_coords[0] / voxel_coords[2]), int(voxel_coords[1] / voxel_coords[2])), markerSize=12, color=(211,211,211), markerType=cv.MARKER_SQUARE, thickness=1, line_type=cv.LINE_AA)
					#cv.circle(undist, (int(voxel_coords[0] / voxel_coords[2]), int(voxel_coords[1] / voxel_coords[2])), 1, (211,211,211), -1)
		
					if undist_b_f_image[int(voxel_coords[0] / voxel_coords[2]), int(voxel_coords[1] / voxel_coords[2])] == 0: V_set[idx] = 0
						# ------------------------ FARE UIL CONRTROLLO-------------- CONTROLLO SE HA SENSO USARE UN ENUMERATE
      
      
				edited_frame = undist
					
			
			end = time.time()
			fps = 1 / (end-start)
   
			avg_fps += fps

			# Get the resized frame
			frame_with_fps_resized = resize_for_laptop(using_laptop, copy.deepcopy(edited_frame))
  
			# Output the frame with the FPS   			
			cv.putText(frame_with_fps_resized, f"{fps:.2f} FPS", (30, 30), cv.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
			cv.imshow(f'Pose Estiamtion of {obj}', frame_with_fps_resized)
			   
			# Save the frame without the FPS count in case of no error
			if pixsl_info.shape[0] >= 6: output_video.write(edited_frame)
   
	 
			prev_frameg = frameg
   
			actual_fps += 1

			key = cv.waitKey(1)
			if key == ord('p'):
				cv.waitKey(-1) 
   
			if key == ord('q'):
				return




			#cv.waitKey(-1)
			   
		
		
  
  
  
  
		resulting_voxels = base_center_voxels.flatten()[np.where(V_set == 1)[0]]
		print(resulting_voxels)
		print(np.where(V_set == 1)[0])
  
   
		print(' DONE')

		print(f'Average FPS is: {str(avg_fps / int(input_video.get(cv.CAP_PROP_FRAME_COUNT)))}\n')

		# Release the input and output streams
		input_video.release()
		output_video.release()
		cv.destroyAllWindows()



if __name__ == "__main__":
	main()
 