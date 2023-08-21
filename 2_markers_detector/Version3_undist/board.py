import cv2 as cv
import numpy as np

from utils import compute_index_and_cc_coords, find_distance_between_points, find_middle_point, sort_vertices_clockwise
from polygon import Polygon

from typing import List, Tuple, Dict


# Set the needed parameters to find the refined corners
winSize_sub = (5, 5)
zeroZone_sub = (-1, -1)
criteria_sub = (cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER, 100, 0.001)


# se the Lucas Kanade parameters
criteria_lk = (cv.TERM_CRITERIA_EPS | cv.TERM_CRITERIA_COUNT, 100, 0.01)
maxlevel_lk = 3


class Board:
    
	def __init__(self, n_polygons: int) -> None:
		self.polygon_list: List[Polygon] = [Polygon() for _ in range(n_polygons)]
		self.tracked_features = np.zeros((0,2), dtype=np.float32)
		self.centroid = None



	def set_centroid(self, centroid):
		if self.centroid is None: self.centroid = centroid
  
  
  	
	def draw_red_polygon(self, image: np.ndarray[np.ndarray[np.ndarray[np.uint8]]]) \
    		->  np.ndarray[np.ndarray[np.ndarray[np.uint8]]]:
		'''
		PURPOSE: draw the red polygon, the cross in point A and the line crossing the polygon by length
		ARGUMENTS: 
			- image (np.ndarray[np.ndarray[np.ndarray[np.uint8]]]): image to edit
		RETURN:
			- (np.ndarray[np.ndarray[np.ndarray[np.uint8]]]): resuting image
		'''	
		for poly in self.polygon_list:
			if poly.cover == False:
				cv.drawContours(image, [np.int32(poly.vertex_coords)], 0, (0, 0, 255), 1, cv.LINE_AA)

				cv.drawMarker(image, np.int32(poly.point_A), (0,255,0), cv.MARKER_CROSS, 20, 1, cv.LINE_AA)

				cv.line(image, np.int32(poly.point_A), np.int32(poly.middle_point), (0, 255, 255), 1, cv.LINE_AA) 
				
				for x, y in poly.vertex_coords:
					cv.circle(image, (int(x), int(y)), 4, poly.color, -1)
					cv.line(image, (int(x), int(y)), self.centroid, poly.color, 1, cv.LINE_AA)
     
		cv.drawMarker(image, self.centroid, color=(255,255,255), markerType=cv.MARKER_CROSS, thickness=2)

		return image
            
       
            
	def draw_green_cross_and_blu_rectangle(self, image: np.ndarray[np.ndarray[np.ndarray[np.uint8]]]) \
    		->  np.ndarray[np.ndarray[np.ndarray[np.uint8]]]:
		'''
		PURPOSE: draw a green cross and a blu rectangle in each circe centre 
		ARGUMENTS: 
			- image (np.ndarray[np.ndarray[np.ndarray[np.uint8]]]): image to edit
		RETURN:
			- (np.ndarray[np.ndarray[np.ndarray[np.uint8]]]): resuting image
		'''	
        
		for poly in self.polygon_list:
			if poly.cover == False:
				for idx, coords in enumerate(reversed(poly.circles_ctr_coords), start=1): 
					start = np.int32(coords[1])
					end = np.int32(coords[0])
					cv.drawMarker(image, (start, end), (0,255,0), cv.MARKER_CROSS, 10 * idx, 1, cv.LINE_AA)
					cv.drawMarker(image, (start, end), (255,0,0), cv.MARKER_SQUARE, 10, 1, cv.LINE_AA)
					
		return image		
  
  
  
	def draw_index(self, image: np.ndarray[np.ndarray[np.ndarray[np.uint8]]]) \
    		->  np.ndarray[np.ndarray[np.ndarray[np.uint8]]]:
		'''
		PURPOSE: draw the polygon index
		ARGUMENTS: 
			- image (np.ndarray[np.ndarray[np.ndarray[np.uint8]]]): image to edit
		RETURN:
			- (np.ndarray[np.ndarray[np.ndarray[np.uint8]]]): resuting image
		'''	
     		
		for index, poly in enumerate(self.polygon_list):
			if poly.cover == False:
				cv.putText(image, str(index), np.int32(poly.point_A), cv.FONT_HERSHEY_SIMPLEX, 1, (0,0,0), 8, cv.LINE_AA)
				cv.putText(image, str(index), np.int32(poly.point_A), cv.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), 2, cv.LINE_AA)
		return image
  


	def draw_stuff(self, image: np.ndarray[np.ndarray[np.ndarray[np.uint8]]]) ->  np.ndarray[np.ndarray[np.ndarray[np.uint8]]]:
		'''
		PURPOSE: apply all the drawing function
		ARGUMENTS: 
			- image (np.ndarray[np.ndarray[np.ndarray[np.uint8]]]): image to edit
		RETURN:
			- (np.ndarray[np.ndarray[np.ndarray[np.uint8]]]): resuting image
		'''	
  
		return self.draw_index(self.draw_green_cross_and_blu_rectangle(self.draw_red_polygon(image)))



	def find_interesting_points(self, thresh: np.ndarray[np.uint8], imgray: np.ndarray[np.uint8]) -> None: #  mask: np.ndarray[np.uint8]
		'''
		PURPOSE: find bood features to track during the frame sequence
		ARGUMENTS: 
			- thresh (np.ndarray[np.uint8]): threshold resut
			- imgray np.ndarray[np.uint8]): gray image
			- mask np.ndarray[np.uint8]) mask to edit
		RETURN: None
		'''	

		# In case I pass a filled arrayb by zeros, this means that we have to recompute the features
		self.tracked_features = np.zeros((0,2), dtype=np.float32)
		
		# Consider only the board exluding all the object area that could be included erroneously
		mask_thresh = np.zeros_like(thresh, dtype=np.uint8)
		mask_thresh[:, 1130:1570] = thresh[:, 1130:1570]

		# Finding the contournsq
		contours, _ = cv.findContours(mask_thresh, cv.RETR_TREE, cv.CHAIN_APPROX_SIMPLE) # [[[X Y]] [[X Y]] ... [[X Y]]]
	
		# Searching through every region selected to find the required polygon.
		for cnt in contours:
			
			# Shortlisting the regions based on there area
			if cv.contourArea(cnt) > 1500.0: # 1650.0

				approx_cnt = cv.approxPolyDP(cnt, 0.015 * cv.arcLength(cnt, True), True) # [[[X Y]] [[X Y]] ... [[X Y]]]
				
				# Checking if the number of sides of the selected region is 5.
				if (len(approx_cnt)) == 5:
					ref_approx_cnt = cv.cornerSubPix(imgray, np.float32(approx_cnt), winSize_sub, zeroZone_sub, criteria_sub)
					self.tracked_features = np.vstack((self.tracked_features, np.squeeze(ref_approx_cnt)))



	def apply_LK_OF(self, prev_frameg: np.ndarray[np.uint8], frameg: np.ndarray[np.uint8], winsize_lk: Tuple[int, int]) -> None:
		'''
		PURPOSE: remove the polygon that are convex, order clockwie and remove the alst polygon by area
		ARGUMENTS: 
			- prev_frameg (np.ndarray[np.uint8]): previous gray frame
			- frameg (np.ndarray[np.uint8]): actual gray frame
			- winsize_lk (Tuple[int, int]): window size
		RETURN: None
		'''	
     
		# Forward Optical Flow
		p1, st, _ = cv.calcOpticalFlowPyrLK(prev_frameg, frameg, self.tracked_features, None, winSize=winsize_lk, maxLevel=maxlevel_lk, criteria=criteria_lk)#, flags=cv.OPTFLOW_LK_GET_MIN_EIGENVALS, minEigThreshold=0.00001)
		
		fb_good = p1[np.where(st == 1)[0]]
  
		self.tracked_features = fb_good
					


	def covered_polygon(self, polygons: np.ndarray[np.int32]) -> None:
		'''
		PURPOSE: apply all the drawing function
		ARGUMENTS: 
			- polygons (np.ndarray[np.int32]): array of index that express the covered polygons
		RETURN: None
		'''	
     
		for id_poly in polygons: self.polygon_list[id_poly].cover = True
  

  
	def compute_markers(self, thresh: np.ndarray[np.uint8], reshaped_clockwise: np.ndarray[np.ndarray[np.ndarray[np.float32]]], \
     		actual_fps: int, marker_reference: Dict[int, Tuple[int, int, int]]):
		'''
		PURPOSE: remove the polygon that are convex, order clockwie and remove the alst polygon by area
		ARGUMENTS:
			- thresh (np.ndarray[np.uint8]):  threshold image
			- reshaped_clockwise (np.ndarray[np.ndarray[np.ndarray[np.float32]]])
			- actual_fps (int): index frmae 
			- marker_reference (Dict[int, Tuple[int, int, int]])): dictionary of the marker reference coordinates
		RETURN:
			- dict_stats_to_return (List[Dict[int, int, np.float64, np.float64, int, int, int]]): lis of dictionary containing the information to save in the .csv file
		'''	
     
		dict_stats_to_return = []		
  
		# np.array of ones in which at the end of the computation will store only the covered polygons
		covered_polys = np.ones((1, 24))[0]

		# Iterate through the reshaped tracked features in clockwise order
		for poly in reshaped_clockwise:

			# Obtain the external point distance between the approximated board centroid and each approximated polygon vertex
			external_points_dict = dict(enumerate(
				list(map(lambda x: find_distance_between_points(x, self.centroid), poly))
			))
		   
			# Obtain the id of the two farthest point from the board centre
			id_external_points = sorted(external_points_dict.items(), key=lambda x:x[1])[-2:]
   

			# Obtain the point between the two farthest point
			middle_point = find_middle_point(poly[id_external_points[0][0]], poly[id_external_points[1][0]])

			# Compute the convex hull of the contour
			hull = np.squeeze(cv.convexHull(poly, returnPoints=False))
   			# The Convex Hull of a shape or a group of points is a tight fitting convex boundary around the points or the shape

			# Get the coordinate of the point A by getting the missing index
			A = np.squeeze(poly[np.squeeze(np.setdiff1d(np.arange(5), hull))])
			#print(A.shape, A)
			if(len(A.shape) == 1):
				index, circles_ctr_coords = compute_index_and_cc_coords(A, middle_point, thresh) 
				#print(index)
				if(index < 24):
					self.polygon_list[index].update_info(False, circles_ctr_coords, poly, A, middle_point)
					covered_polys[index] = 0

					# Get the X, Y and Z marker reference 2D coordinates for the polygon with given index
					X, Y, Z = marker_reference[index] 
   
					dict_stats_to_return.append({'frame': actual_fps, 'mark_id': index, 'Px': A[0], 'Py': A[1], 'X': X, 'Y': Y, 'Z': Z})

   
		# Set the cover cover attributo to true on all cover polygons
		self.covered_polygon(np.where(covered_polys == 1)[0])
   
		return dict_stats_to_return
	
 
 
	def get_clockwise_vertices_initial(self) -> np.ndarray[np.ndarray[np.ndarray[np.float32]]]:
		'''
		PURPOSE: reshape the obtained features, sort them in clockwise order and remove the last polygon by area
		ARGUMENTS: None
		RETURN:
  			- (np.ndarray[np.ndarray[np.ndarray[np.float32]]]): sorted vertices polygon
		'''	
     
		self.tracked_features = sort_vertices_clockwise(self.tracked_features, self.centroid)
		
		self.tracked_features = self.tracked_features[:int(self.tracked_features.shape[0] // 5) * 5, :]
			
		reshaped_clockwise = np.reshape(self.tracked_features, (int(self.tracked_features.shape[0] // 5), 5, 2))
  
		# I have to sort clockwise the alst polygon in order to compute correctly the contourArea
		if(cv.contourArea(sort_vertices_clockwise(reshaped_clockwise[-1,:,:])) <= 1500.0):
			reshaped_clockwise = reshaped_clockwise[:reshaped_clockwise.shape[0] - 1, :, :]
		
		return np.array([sort_vertices_clockwise(poly) for poly in reshaped_clockwise])