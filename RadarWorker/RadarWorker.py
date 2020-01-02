import logging, math, os, config, datetime, requests
from workers import MapWorker
from txtparsing import DataWorker


LOC_FOLS = config.LOC_FOLS
TAG = 'RadarWorker - '

# General - Only works for years after 2011

# Class to manage program interaction with radar data
#       - Furnishes reflectivity at a pixel location/lat-lon tuple
#       - Pulls radar data 

# Attributes to implement:
#       - sim_time, map_path (filepath to local map and overlay)
class RadarWorker:
    IEM_URL = 'https://mesonet.agron.iastate.edu/archive/data/'

    # Constructor
    def __init__(self, sim_time):
        self.sim_time = sim_time
        self.__radar_stations = []
        self.__http_errors = 0

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

    def pull_data(self):
        self.cl_wd()
        url_data = self._generate_url_data()

        logging.info(TAG+'Downloading the png file')
        try:
            request = requests.get(url_data[0])
        except:
            logging.error(TAG+'IEM not furnishing data... try again later.')
        with open(LOC_FOLS['nexrad']+url_data[2]+'.png', 'wb') as file:
            file.write(request.content)
            self._check_request_completion(request)

        logging.info(TAG+'Downloading the wld file')
        try:
            request = requests.get(url_data[1])
        except:
            logging.error(TAG+'IEM not furnishing data... try again later.')
        with open(LOC_FOLS['nexrad']+url_data[2]+'.txt', 'wb') as file:
            file.write(request.content)
            self._check_request_completion(request)
        

    def create_overlay_image(self, bot_left, top_right):
        return None

    def get_reflectivity(self, gps_location):
        # Code to get the reflectivity for a given location at the sim_time
        return None

    def _get_reflectivity_of_pixel(self, pixel_location):
        # Code to get the reflectivity represented by a certain pixel
        return None

    def __str__(self):
        printout  = '**********Radar Worker**********\n'
        printout += 'Time: ' + str(self.__sim_time)
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
    