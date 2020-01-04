import logging, math, os, config, datetime, requests, txtparsing 
from workers import MapWorker
from txtparsing import DataWorker
from workers import MapWorker 
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
        lon_dif = gps_coor[1] - self.__iem_range[1][0]
        lat_dif = self.__iem_range[0][1] - gps_coor[0]
        im  = Image.open(self.__img_path)
        im_width, im_height = im.size

        x = int(lon_dif / self.__pixel_width)
        y = int(lat_dif / self.__pixel_width)
        logging.info('Converted gps coordinate to: x:{} y:{}'.format(x, y))
        return (x, y)

    # Overlays nexrad data over weather tiles created by a MapWorker
    # Areas with no data available are overlayed with a red tint
    def create_overlay_image(self, map_worker):
        logging.info(TAG+'creating a map overlayed with nexrad data')
        mp_lat_r = map_worker.gps_range[0]
        mp_lon_r = map_worker.gps_range[1]

        map_img = Image.open(map_worker.tilepath)
        mp_width, mp_height = map_img.size

        iem = Image.open(self.__img_path).convert("RGBA")
        iem_width, iem_height = iem.size

        # Top right pixel point in iem image (left_top if gps)
        iem_min_x, iem_min_y = self.gps_to_pixel((mp_lat_r[1], mp_lon_r[0])) 
        iem_max_x, iem_max_y = self.gps_to_pixel((mp_lat_r[0], mp_lon_r[1]))

        part_in_range = True
        if (iem_max_x > iem_width and iem_min_x > iem_width) or iem_max_x < 0:
            part_in_range = False
        elif (iem_max_y > iem_height and iem_min_y > iem_height) or iem_max_y < 0:
            part_in_range = False

        # Figure out how many pixels are needed for the red no-data zone
        add_x, add_y = ([], [])
        if part_in_range:
            # Handle the values for 'x'
            if iem_min_x < 0:
                add_x.append(iem_min_x * -1)
                iem_min_x = 0
            else:
                add_x.append(0)
            if iem_max_x > iem_width:
                add_x.append(iem_max_x - iem_width)
                iem_max_x = iem_width
            else:
                add_x.append(0)

            # Handle the values for 'y'
            if iem_min_y < 0:
                add_y.append(iem_min_y * -1)
                iem_min_y = 0
            else:
                add_y.append(0)
            if iem_max_y > iem_height:
                add_y.append(iem_max_y - iem_height)
                iem_max_y = iem_height
            else:
                add_y.append(0)
            
            # Create a blank, transparent canvas to create ovelay on
            canv_width = (iem_max_x - iem_min_x) + sum(add_x)
            canv_height = (iem_max_y - iem_min_y) + sum(add_y)
            canvas = Image.new('RGBA', (canv_width, canv_height), color = (0,0,0,0)) 

            # Create a crop of data needed from IEM's png
            crop = iem.crop((iem_min_x, iem_min_y, iem_max_x, iem_max_y))
            crop = self.apply_transparency_filter(crop)

            # Add all red overlays
            canvas.paste(crop, (add_x[0], add_y[0]), crop)
            red = Image.new('RGBA', (crop.size[0], add_y[0]), color=(230, 14, 14, 90))
            canvas.paste(red, (add_x[0], 0), red)
            red = Image.new('RGBA', (add_x[0], canv_height), color=(230, 14, 14, 90))
            canvas.paste(red, (0, 0), red)
            red = Image.new('RGBA', (add_x[1], canv_height), color=(230, 14, 14, 90))
            canvas.paste(red, ((iem_max_x - iem_min_x) + add_x[0], 0), red)
            red = Image.new('RGBA', (crop.size[0], add_y[1]), color=(230, 14, 14, 90))
            canvas.paste(red, (add_x[0], (iem_max_y - iem_min_y) + add_y[0]), red)

            # Paste data and filter onto map
            canvas = canvas.resize(map_img.size, Image.ANTIALIAS)
            map_img.paste(canvas, (0,0), canvas)
        else:
            canvas = Image.new('RGBA', (200, 100), color = (230, 14, 14, 90))
            canvas = canvas.resize(map_img.size, Image.ANTIALIAS)
            map_img.paste(canvas, (0,0), canvas)

        map_img.save(LOC_FOLS['map']+'overlay+stitched.png', 'PNG')
        logging.info(TAG+'completed map w/overlay')

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
    def apply_transparency_filter(img):
        logging.info(TAG+'making all black pixels transparent')
        img = img.convert('RGBA')
        data = img.getdata()

        new_data = list()
        for item in data:
            if item[0] == 0 and item[1] == 0 and item[2] == 0:
                new_data.append((0, 0, 0, 0))
            else:
                new_data.append(item)

        img.putdata(new_data)
        return img

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