import logging, math, os, config, datetime, requests, txtparsing 
from workers import MapWorker
from txtparsing import DataWorker
from PIL import Image


LOC_FOLS = config.LOC_FOLS
TAG = 'RadarWorker - '

# Only works for years after 2011
# Makes use of data from IEM

# Class to manage program interaction with radar data
#       - Furnishes reflectivity at a pixel location/lat-lon tuple
#       - Pulls radar data 
#       - Contains methods to create overlays for the MapWorker
class RadarWorker:
    IEM_URL = 'https://mesonet.agron.iastate.edu/archive/data/'

    # Constructor
    def __init__(self, sim_time):
        self.sim_time = sim_time
        self.__radar_stations = []
        self.__http_errors = 0
        self.__img_path = None
        self.__wld_path = None

        worker = DataWorker(LOC_FOLS['meta']+'nexrad-stations-template.txt')
        worker.quicksort_lg(LOC_FOLS['meta']+'nexrad-stations.txt',
                            LOC_FOLS['meta']+'nexrad-stations-sorted.txt',
                            'longitude')
        worker.replace(LOC_FOLS['meta']+'nexrad-stations.txt',
                       LOC_FOLS['meta']+'nexrad-stations-sorted.txt')
        meta_data = worker.get_vals(LOC_FOLS['meta']+'nexrad-stations.txt', 
                                    ['icao', 'state', 'elevation', 'latitude', 'longitude'])
        for station_list in meta_data:
            self.__radar_stations.append(RadarStation(station_list[0], station_list[1],
                                                      station_list[2], station_list[3],
                                                      station_list[4]))

    @property 
    def sim_time(self):
        return self.__sim_time

    # Ensures that time falls in 5 minute increments
    @sim_time.setter
    def sim_time(self, time):
        mod5 = time.minute % 5
        if mod5 is 0 and time.second is 0:
            self.__sim_time = time
        else:
            minute = time.minute
            second = time.second
            if second is not 0 and second >= 30:
                minute += 1
                mod5 = minute % 5

            if mod5 < 3:
                while minute % 5 is not 0:
                    minute -= 1
            else:
                while minute % 5 is not 0:
                    minute += 1
        self.__sim_time = time.replace(minute=minute, second=0)

    # Generates urls for data pulls
    def _generate_url_data(self):
        gen_url  = self.IEM_URL + str(self.__sim_time.year) + '/'
        gen_url += self.s_ext(str(self.__sim_time.month), 2) + '/'
        gen_url += self.s_ext(str(self.__sim_time.day), 2) + '/GIS/uscomp/'

        filename  = 'n0q_' + str(self.__sim_time.year) + self.s_ext(str(self.__sim_time.month), 2)
        filename += self.s_ext(str(self.__sim_time.day), 2) + self.s_ext(str(self.__sim_time.hour), 2)
        filename += self.s_ext(str(self.__sim_time.second), 2) 
        gen_url += filename
        
        png_url = gen_url + '.png'
        logging.info(TAG+'generated png url: ' + png_url)

        wld_url = gen_url + '.wld'
        logging.info(TAG+'generated wld url: ' + wld_url)

        return [png_url, wld_url, filename]

    def _check_request_completion(self, request):
        if request.status_code is not 200:
            self.__http_errors += 1
            logging.error(TAG+'*****FAILED TO DOWNLOAD FILE*****')
            if self.__http_errors >= 25:
                raise Exception('Too many failed downloads: {} downloads failed'.format(self.__http_errors))

    # Method to pull wld file as well as png file from IEM
    def pull_data(self):
        self.cl_wd()
        url_data = self._generate_url_data()

        logging.info(TAG+'Downloading the png file')
        try:
            request = requests.get(url_data[0])
        except:
            logging.error(TAG+'IEM not furnishing nexrad data... try again later.')
        with open(LOC_FOLS['nexrad']+url_data[2]+'.png', 'wb') as file:
            file.write(request.content)
            self._check_request_completion(request)
            self.__img_path = LOC_FOLS['nexrad']+url_data[2]+'.png'

        logging.info(TAG+'Downloading the wld file')
        try:
            request = requests.get(url_data[1])
        except:
            logging.error(TAG+'IEM not furnishing wld data... try again later.')
        with open(LOC_FOLS['nexrad']+url_data[2]+'.txt', 'wb') as file:
            file.write(request.content)
            self._check_request_completion(request)
            self.__wld_path = LOC_FOLS['nexrad']+url_data[2]+'.txt'
        self._process_wld() 
    
    # Method to process the data stored in the wld file for the downloaded IEM data
    def _process_wld(self):
        logging.info(TAG+'Processing the wld file pulled correlating to IEM data')
        wld_file = self.__wld_path
        
        # Fill a local array with wld data
        wld_data = []
        with open(wld_file, 'r') as reader:
            line = reader.readline()
            while line:
                wld_data.append(line.rstrip())
                line = reader.readline()

        # Convert all wld data in dictionary to float values
        for i, data in enumerate(wld_data):
            if data[0] == '-' or data[0] == '+':
                wld_data[i] = txtparsing.DataWorker.str_to_flt(wld_data[i])
            else:
                wld_data[i] = float(wld_data[i])
        
        # Make sure map skew is zero, not handled in this program
        if wld_data[1] != 0 or wld_data[2] != 0:
            raise Exception('wld data is skewed')

        # Make sure the pixels are square
        if wld_data[0] != -wld_data[3]:
            raise Exception('rectangular pixels in IEM data, add code to handle')

        # Load data into the object, for other functions to make use of
        self.__pixel_width = wld_data[0]

        im  = Image.open(self.__img_path)
        width, height = im.size
        self.__iem_range = ((wld_data[5] - height*self.__pixel_width, wld_data[5]),
                            (wld_data[4], wld_data[4] + width*self.__pixel_width))
        logging.info(TAG+'GPS range of IEM data: {}'.format(self.__iem_range))
            
    # Method to convert gps coordinates to pixel coordinates for IEM image pulled
    # Assumes that the pixel requested is in the data range
    def gps_to_pixel(self, gps_coor):
        range = self.__iem_range
        lon_dif = abs(gps_coor[1] - self.__iem_range[1][0])
        lat_dif = abs(self.__iem_range[0][1] - gps_coor[0])
        im  = Image.open(self.__img_path)
        im_width, im_height = im.size

        x = int(lon_dif / self.__pixel_width)
        y = int(lat_dif / self.__pixel_width)
        logging.info('Converted gps coordinate to: x:{} y:{}'.format(x, y))
        return (x, y)

    # Creates a transparent-background overlay to lay on an image with the gps bounds 
    # passed as arguments
    def create_overlay_image(self, bot_left, top_right, map_path):
        logging.info('creating the overlay image')
        bot_left_pix = self.gps_to_pixel(bot_left)
        top_right_pix = self.gps_to_pixel(top_right)
        img  = Image.open(self.__img_path)
        region = img.crop((bot_left_pix[0], top_right_pix[1], top_right_pix[0], bot_left_pix[1]))

        region.save(LOC_FOLS['map']+'overlay.png', 'PNG')
        self.apply_transparency_filter(LOC_FOLS['map']+'overlay.png')
        self.layer_images(map_path, LOC_FOLS['map']+'overlay.png', LOC_FOLS['map']+'stitched+overlay.png')

    def get_reflectivity(self, gps_location):
        # Code to get the reflectivity for a given location at the sim_time
        return None

    def _get_reflectivity_of_pixel(self, pixel_location):
        # Code to get the reflectivity represented by a certain pixel
        return None

    # A to-string method 
    def __str__(self):
        printout  = '**********Radar Worker**********\n'
        printout += 'Time: ' + str(self.__sim_time)
        if self.__img_path is not None:
            printout += '\n__img_path: {}'.format(self.__img_path)
        if self.__wld_path is not None:
            printout += '\n__wld_path: {}'.format(self.__wld_path)

        return printout

    @staticmethod
    def layer_images(bottom, top, final):
        top = Image.open(top)
        bottom = Image.open(bottom)

        top = top.resize(bottom.size, Image.ANTIALIAS)

        bottom.paste(top, (0, 0), top)
        bottom.save(final,'PNG')

    # Simple sign-extension method
    @staticmethod
    def s_ext(str, length):
        while len(str) != length:
            str = '0'+str
        return str

    # Clears the downloaded files from local directory
    @staticmethod
    def cl_wd():
        logging.info(TAG+'clearing downloaded files')
        for file in os.listdir(LOC_FOLS['nexrad']):
            os.unlink(LOC_FOLS['nexrad']+file)

    @staticmethod
    def apply_transparency_filter(path):
        logging.info(TAG+'making all black pixels transparent')
        img  = Image.open(path)
        img = img.convert('RGBA')
        data = img.getdata()

        new_data = list()
        for item in data:
            if item[0] == 0 and item[1] == 0 and item[2] == 0:
                new_data.append((0, 0, 0, 0))
            else:
                new_data.append(item)

        img.putdata(new_data)
        img.save(path, 'PNG')

# Class to represent a radar station, originally in NEXRADWorker
class RadarStation():
    def __init__(self, icao, state, elevation, latitude, longitude):
        self.icao = icao
        self.state = state
        self.elevation = elevation
        self.latitude = latitude
        self.longitude = longitude

    @property
    def elevation(self):
        return self._elevation

    @property
    def latitude(self):
        return self._latitude

    @property
    def longitude(self):
        return self._longitude

    @elevation.setter
    def elevation(self, elevation):
        self._elevation = int(elevation)

    @latitude.setter
    def latitude(self, latitude):
        self._latitude = float(latitude)

    @longitude.setter
    def longitude(self, longitude):
        self._longitude = float(longitude)

    def __str__(self):
        printout  = '*****' + self.icao  + '*****' + ' \n'
        printout += 'Longitude: ' + str(self.longitude) + '\n'
        printout += 'Latitude: ' + str(self.latitude) + '\n'
        return printout
    
# Improvements:
# Support for mapping in ranges that broach into Canada and South America, as of now cause program crash