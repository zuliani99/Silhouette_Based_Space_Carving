# Polygon calss that store useful information

class Polygon:
	def __init__(self) -> None:
		self.cover = True
		self.circles_ctr_coords = None
		self.vertex_coords = None
		self.point_A = None
		self.middle_point = None
	
	def update_info(self, cover, circles_ctr_coords, vertex_coords, point_A, middle_point):
		self.cover = cover
		self.circles_ctr_coords = circles_ctr_coords
		self.vertex_coords = vertex_coords
		self.point_A = point_A
		self.middle_point = middle_point