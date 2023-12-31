import numpy as np
import cv2 as cv
import time
import copy
import os
import argparse


from utils import resize_for_laptop, draw_origin, draw_cube

# Objects cube_half_edge
parameters = {
	'obj01.mp4': {'cube_half_edge': 55},
	'obj02.mp4': {'cube_half_edge': 60},
	'obj03.mp4': {'cube_half_edge': 75},
	'obj04.mp4': {'cube_half_edge': 55},
}



def main(using_laptop: bool) -> None:
	'''
	PURPOSE: function that start the whole computation
	ARGUMENTS:
		- using_laptop (bool): boolean variable to indicate the usage of an HD laptop or not
	RETURN: None
	'''
 
	# Check if the user run the camera calibration program before
	if not os.path.exists('./calibration_info/cameraMatrix.npy') or not os.path.exists('./calibration_info/dist.npy'):
		print('Please, before running the pose estimation, execute the camera calibration program.')
		return

	# Load the camera matrix and distorsion coefficients
	camera_matrix = np.load('./calibration_info/cameraMatrix.npy')
	dist = np.load('./calibration_info/dist.npy')
 
	centroid_axes = np.float32([[20,0,0], [0,20,0], [0,0,30]]).reshape(-1,3)
	 
	# Iterate for each object
	for obj, hyper_param in parameters.items():
	  
		print(f'Pose Estiamtion of {obj}...')
  
		# Create the VideoCapture object
		input_video = cv.VideoCapture(f"../data/{obj}")
		  
		# Get video properties
		frame_width = int(input_video.get(cv.CAP_PROP_FRAME_WIDTH))
		frame_height = int(input_video.get(cv.CAP_PROP_FRAME_HEIGHT))

		# Get the new camera intrinsic matrix based on the free scaling parameter
		newCameraMatrix, roi = cv.getOptimalNewCameraMatrix(camera_matrix, dist, (frame_width, frame_height), 1, (frame_width, frame_height))

		actual_fps = 0.0
		avg_fps = 0.0
		obj_id = obj.split('.')[0]
		
		edited_frame = None
  
		cube_half_edge = hyper_param['cube_half_edge']
  
		cube_vertices = np.float32([
											[-cube_half_edge, -cube_half_edge, 70], [-cube_half_edge, cube_half_edge, 70],
											[cube_half_edge ,cube_half_edge, 70], [cube_half_edge, -cube_half_edge, 70],
											[-cube_half_edge, -cube_half_edge, 70 + cube_half_edge * 2],[-cube_half_edge, cube_half_edge, 70 + cube_half_edge * 2],
											[cube_half_edge, cube_half_edge, 70 + cube_half_edge * 2],[cube_half_edge, -cube_half_edge, 70 + cube_half_edge * 2]
										])

  
		# Create output video writer initialized at None since we do not know the undistorted resolution
		output_video = None
  
		markers_info = np.loadtxt(f'../output_part2/{obj_id}/{obj_id}_marker.csv', delimiter=',', dtype=str)[1:,:].astype(np.float32)

		while True:
			start = time.time()
			   
			# Extract a frame
			ret, frame = input_video.read()

			if not ret:	break

			# Undistort the image
			undist = cv.undistort(frame, camera_matrix, dist, None, newCameraMatrix)	
			x, y, w, h = roi
			undist = undist[y:y+h, x:x+w] # Adjust the image resolution
    
			# Update width, height and output_video
			if output_video is None: 
				frame_width, frame_height = undist.shape[1], undist.shape[0] 
				output_video = cv.VideoWriter(f'../output_part3/{obj_id}_cube.mp4', cv.VideoWriter_fourcc(*'mp4v'), input_video.get(cv.CAP_PROP_FPS), (frame_width, frame_height))

			# Get the actual markers informations from the csv file
			csv_frame_index = np.where(markers_info[:,0] == actual_fps)[0]
      

			edited_frame = undist


			if csv_frame_index.shape[0] > 6:
       
				twoD_points = markers_info[csv_frame_index,2:4]
				threeD_points = markers_info[csv_frame_index,4:7]

				# Find the rotation and translation vectors
				ret, rvecs, tvecs = cv.solvePnP(objectPoints=threeD_points, imagePoints=twoD_points, cameraMatrix=camera_matrix, distCoeffs=dist, flags=cv.SOLVEPNP_IPPE)

	 			# Obtain the projection of the board centroid with axes and the cube that will inglobe the object
				imgpts_centroid, _ = cv.projectPoints(objectPoints=centroid_axes, rvec=rvecs, tvec=tvecs, cameraMatrix=camera_matrix, distCoeffs=dist)
				imgpts_cube, _ = cv.projectPoints(objectPoints=cube_vertices, rvec=rvecs, tvec=tvecs, cameraMatrix=camera_matrix, distCoeffs=dist)
			   		  	 
				# Draw the projected cube and centroid
				edited_frame = draw_origin(undist, (1259, 520), np.int32(imgpts_centroid))
				edited_frame = draw_cube(edited_frame, np.int32(imgpts_cube))
      					

			end = time.time()
			fps = 1 / (end-start)
   
			avg_fps += fps

			# Get the resized frame
			frame_with_fps_resized = resize_for_laptop(using_laptop, copy.deepcopy(edited_frame))
  
       
			# Output the frame with the FPS   			
			cv.putText(frame_with_fps_resized, f"{fps:.2f} FPS", (30, 30), cv.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
			cv.imshow(f'Pose Estiamtion of {obj}', frame_with_fps_resized)
			   
			# Save the frame without the FPS count in case of no error
			output_video.write(edited_frame)
   
	 
			actual_fps += 1

			key = cv.waitKey(1)
			if key == ord('p'):
				cv.waitKey(-1) 
   
			if key == ord('q'):
				return
			   
   
		print(' DONE')
		print(f'Average FPS is: {str(avg_fps / int(input_video.get(cv.CAP_PROP_FRAME_COUNT)))}\n')

		# Release the input and output streams
		input_video.release()
		output_video.release()
		cv.destroyAllWindows()




if __name__ == "__main__":
    
    # Get the console arguments
	parser = argparse.ArgumentParser(prog='Assignment3_Pose_Estimation', description="Pose Estimation")
	parser.add_argument('--hd_laptop', dest='hd_laptop', default=False, action='store_true', help="Using a 720p resolution")
	args = parser.parse_args()
 
	main(args.hd_laptop)
 