import numpy as np
import cv2 as cv
import time
import copy
import argparse
import os

from utils import set_marker_reference_coords, resize_for_laptop, write_ply_file
from background_foreground_segmentation import apply_segmentation
from board import Board
from voxels_cube import VoxelsCube


# Objects cube_half_edge parameters
parameters = {
	'obj01.mp4': {'cube_half_edge': 55},
	'obj02.mp4': {'cube_half_edge': 60},
	'obj03.mp4': {'cube_half_edge': 75},
	'obj04.mp4': {'cube_half_edge': 55},
}



def main(using_laptop: bool, voxel_cube_edge_dim: int) -> None:
	'''
	PURPOSE: function that start the whole computation
	ARGUMENTS:
		- using_laptop (bool): boolean variable to indicate the usage of an HD laptop or not
		- voxel_cube_edge_dim (int): pixel dimension of a voxel cube edge
	RETURN: None
	'''
	 
	# Set the marker reference coordinates of the 24 polygonls
	marker_reference = set_marker_reference_coords()
	
	# Check if the user run the camera calibration program before
	if not os.path.exists('./calibration_info/cameraMatrix.npy') or not os.path.exists('./calibration_info/dist.npy'):
		print('Please, before running the project, execute the camera calibration program.')
		return

	# Load the camera matrix and distorsion coefficients
	camera_matrix = np.load('./calibration_info/cameraMatrix.npy')
	dist = np.load('./calibration_info/dist.npy')
  
  
	# Iterate for each object
	for obj, hyper_param in parameters.items():
		
		print(f'Space Carving of {obj}...')
  
		# Create the VideoCapture object
		input_video = cv.VideoCapture(f"../data/{obj}")
		  
		# Get video properties
		frame_width = int(input_video.get(cv.CAP_PROP_FRAME_WIDTH))
		frame_height = int(input_video.get(cv.CAP_PROP_FRAME_HEIGHT))

		actual_fps = 0
		avg_fps = 0.0
		avg_rmse = 0.0
		obj_id = obj.split('.')[0]

		prev_frameg = None
  
		cube_half_edge = hyper_param['cube_half_edge']

		# Create the Board object
		board = Board(n_polygons=24)

		# Create the VoxelsCube object
		voxels_cube = VoxelsCube(cube_half_edge=cube_half_edge, voxel_cube_edge_dim=voxel_cube_edge_dim, camera_matrix=camera_matrix, dist=dist, frame_width=frame_width, frame_height=frame_height)
  
		# Create output video writer initialized at None since we do not know the undistorted resolution
		output_video = None

		# Get the new camera intrinsic matrix based on the free scaling parameter
		voxels_cube.get_newCameraMatrix()

		while True:
      
			start = time.time()
			   
			# Extract a frame
			ret, frame = input_video.read()

			if not ret:	break
   
			# Get the undistorted frame
			undist_frame = voxels_cube.get_undistorted_frame(frame)

			# Update width, height and output_video
			if output_video is None: 
				frame_width, frame_height = undist_frame.shape[1], undist_frame.shape[0] 
				output_video = cv.VideoWriter(f'../output_project/{obj_id}/{obj_id}.mp4', cv.VideoWriter_fourcc(*'mp4v'), input_video.get(cv.CAP_PROP_FPS), (frame_width, frame_height))
			
			# Get the gray frame
			frameg = cv.cvtColor(undist_frame, cv.COLOR_BGR2GRAY)
   
			# Get the thresholded frame by Otsu Thresholding 
			_, thresh = cv.threshold(frameg, 0, 255, cv.THRESH_BINARY + cv.THRESH_OTSU)
   
			   
			if(actual_fps % 5 == 0): 
				# Each 5 frames recompute the whole features to track
				board.find_interesting_points(thresh, frameg)
			else:
				# The other frame use the Lucas-Kanade Optical Flow to estimate the postition of the tracked features based on the previous frame
				board.apply_LK_OF(prev_frameg, frameg, (20, 20))

			# Order the detected features in clockwise order to be able to print correctly
			reshaped_clockwise = board.get_clockwise_vertices()   

			# Obtain the np.array of markers information
			markers_info = board.compute_markers(thresh, reshaped_clockwise, marker_reference)
   

			edited_frame = undist_frame
   

			if markers_info.shape[0] > 6:

				# Draw the marker detector stuff
				edited_frame = board.draw_stuff(edited_frame)
				
				# Extract the indices ID, the 2D and 3D points
				indices_ID = markers_info[:,0]
				twoD_points = markers_info[:,1:3]
				threeD_points = markers_info[:,3:6]
    
    
				# Get the projection of the board centroid, of the cube vertices and of the voxels centroids
				imgpts_centroid, imgpts_cube = voxels_cube.apply_projections(twoD_points, threeD_points)

				# Get the RMS pixel error of reprojection points for the actual frame
				avg_rmse += voxels_cube.compute_RMSE(indices_ID, marker_reference, twoD_points)
    
				# Apply the segmentation on the undistorted frame
				undist_mask = apply_segmentation(obj, undist_frame)

				# Draw the projected cube and centroid axes
				edited_frame = board.draw_origin(edited_frame, np.int32(imgpts_centroid))
				edited_frame = voxels_cube.draw_cube(edited_frame, np.int32(imgpts_cube))
    
				# Update the binary array of foreground voxels and draw the background
				edited_frame = voxels_cube.set_background_voxels((frame_width, frame_height), undist_mask, edited_frame)
    
				
			end = time.time()
			fps = 1 / (end-start)
   
			avg_fps += fps

			# Get the resized frame
			frame_with_fps_resized = resize_for_laptop(using_laptop, copy.deepcopy(edited_frame))
  
			# Output the frame with the FPS   			
			cv.putText(frame_with_fps_resized, f"{fps:.2f} FPS", (30, 30), cv.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
			cv.imshow(f'Space Carving of {obj}', frame_with_fps_resized)
			   
			# Save the frame without the FPS count
			output_video.write(edited_frame)
   
	 		# Update the previous gray frame
			prev_frameg = frameg
   
			actual_fps += 1


			key = cv.waitKey(1)
			if key == ord('p'): cv.waitKey(-1) 
   
			if key == ord('q'): return


		print(' DONE')
		print(f'Average FPS is: {str(avg_fps / int(input_video.get(cv.CAP_PROP_FRAME_COUNT)))}')
		print(f'Average Reprojection RMS Pixel Error is: {str(avg_rmse / int(input_video.get(cv.CAP_PROP_FRAME_COUNT)))}')


		# Release the input and output streams
		input_video.release()
		output_video.release()
		cv.destroyAllWindows()

		print('Saving PLY file...')
  
		# Get the voxels cube coordinates and faces to write a PLY file
		voxels_cube_coords, voxels_cube_faces = voxels_cube.get_cubes_coords_and_faces()
		# Save in a .ply file
		write_ply_file(obj_id, voxels_cube_coords, voxels_cube_faces)
		print(' DONE\n')



if __name__ == "__main__":
    
    # Get the console arguments
	parser = argparse.ArgumentParser(prog='SpaceCarving', description='Space Carving Project')
	parser.add_argument('--hd_laptop', dest='hd_laptop', default=False, action='store_true', help='Using a 720p resolution')
	parser.add_argument('voxel_cube_edge_dim', type=int, help='Dimension of a voxel cube edge')
	args = parser.parse_args()
	
	if(args.voxel_cube_edge_dim < 0): raise ValueError('The voxel_cube_edge_dim must be a positive integer number')

	main(args.hd_laptop, args.voxel_cube_edge_dim)
 