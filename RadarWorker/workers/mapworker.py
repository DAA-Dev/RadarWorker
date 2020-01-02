import requests, logging, os, config, Pillow
import numpy as np

TAG = 'MapWorker - '

LOC_FOLS = config.LOC_FOLS

# Manages ONE TILE ONLY, either rectangular or square
class MapWorker():
    def __init__(self, gps_coordinate, zoom_level=8, rectangular_tiles=True):
        self.cl_wd()
        # These attributes should never change
        self.__zoom_level = zoom_level
        self.__rectangular_tiles = rectangular_tiles
        
        # These attributes will be dynamically updated
        self.__gps_coordinate = gps_coordinate
        self.__gps_range = ()
        self.__tilepath = ''
        self.update_tile()

    @property
    def tilepath(self):
        return self.__tilepath

    def update_tile(self):
        if self.__rectangular_tiles:
            self.__tilepath = self.get_rect_tile()
        else:
            self.__tilepath = self.get_tile()

    # Method that gets the tile to which a gps coordinate resides in
    # Dowloads and saves the tiles if it is not present in the working directory for the worker
    def get_tile(self):
        power = self.__zoom_level + 1
        x_tiles = 2**power
        y_tiles = 2**self.__zoom_level
        possible_x = (0, x_tiles - 1)
        possible_y = (0, y_tiles - 1)

        lon_increment = 360 / x_tiles
        lat_increment = 180 / y_tiles

        def generate_range_x(x):
            return (x * lon_increment - 180, x * lon_increment + lon_increment - 180)

        def generate_range_y(y):
            return (y * lat_increment - 90, y * lat_increment + lat_increment - 90)

        def binary_search(left, right, value, range_function):
            middle = int((right + left) / 2)

            mid_range = range_function(middle)
            if value <= mid_range[1] and value >= mid_range[0]:
                return middle
            elif value > mid_range[1]:
                return binary_search(middle + 1, right, value, range_function)
            else:
                return binary_search(left , middle - 1, value, range_function)
    
        logging.info(TAG+'beginning binary search for proper tile')
        found_x = binary_search(possible_x[0], possible_x[1], self.__gps_coordinate[1], generate_range_x)
        found_y = binary_search(possible_y[0], possible_y[1], self.__gps_coordinate[0], generate_range_y)
        found_y = possible_y[1] - found_y

        self.__gps_range = ((90 - found_y * lat_increment + lat_increment, 90 - found_y * lat_increment), 
                     (found_x * lon_increment - 180, found_x * lon_increment + lon_increment - 180))
        
        return self.pull_tile(found_x, found_y, self.__zoom_level)

    # Method to combine two map tiles, with the gps coordinate specified located in the left tile
    def get_rect_tile(self):
        left_path = self.get_tile()
        logging.info(TAG+'the path of the left gps tile is {}'.format(left_path))

        ind = left_path.index('+') - 1
        while self.check_int(left_path[ind-1]):
            ind -= 1
        x = int(left_path[ind : (left_path.index('+'))])
        logging.info(TAG+'the x value of the left gps tile is {}'.format(x))

        ind = left_path.index('+') + 1
        while self.check_int(left_path[ind+1]):
            ind += 1
        y = int(left_path[left_path.index('+')+1:ind+1])
        logging.info(TAG+'the y value of the right gps tile is {}'.format(y))

        right_path = pull_tile(x + 1, y, self.__zoom_level)

        # Code for new GPS range calculation
        


    # Handles the dowload and save of a requested tile
    @staticmethod
    def pull_tile(x, y, z):
        # Checks to see if the requested map tile has already been downloaded
        for file in os.listdir(LOC_FOLS['map']):
            if file == '{}+{}.png'.format(x, y):
                logging.info(TAG+'file found locally, no download needed')
                return LOC_FOLS['map']+'{}+{}.png'.format(x, y)

        logging.info(TAG+'beginning the download of requested map tile')
        url = 'https://tile.gbif.org/{}/{}/{}/{}/{}{}{}'.format('4326', 'omt', z, x, 
                                                                y, '@4x.png', '?style=osm-bright')
        request = requests.get(url)
        with open(LOC_FOLS['map']+'{}+{}.png'.format(x, y), 'wb') as file:
                file.write(request.content)
                if request.status_code is not 200:
                    logging.error('*****FAILED TO DOWNLOAD MAP TILE*****')
        return LOC_FOLS['map']+'{}+{}.png'.format(x, y)

    # Clears the downloaded files from local directory for NEXRAD data
    @staticmethod
    def cl_wd():
        logging.info(TAG+'clearing downloaded files in the mapping directory')
        for file in os.listdir(LOC_FOLS['map']):
                os.unlink(LOC_FOLS['map']+file)

    # Checks to see if a string is an int
    @staticmethod
    def check_int(word):
        try:
            int(word)
            return True
        except:
            return False