from geojson import Feature, FeatureCollection
from geojson import dumps, Point

import luigi
from LuigiUtils import TimestampedLocalTarget, MTimeMixin
import Utils
import Config
import CalculateZooms
import Popularity



class ZoomGeoJSONWriterCode(MTimeMixin, luigi.ExternalTask):
    def output(self):
        return(TimestampedLocalTarget(cartograph.ZoomGeoJSONWriter.__file__))

class CreateLabelsFromZoom(MTimeMixin, luigi.Task):
    '''
    Generates geojson data for relative zoom labelling in map.xml
    '''
    def output(self):
        config = Config.get()
        return TimestampedLocalTarget(config.get("MapData", "title_by_zoom"))

    def requires(self):
        return (
                CalculateZooms.ZoomLabeler(),
                Popularity.PopularityIdentifier(),
                ZoomGeoJSONWriterCode(),
         )


    def run(self):
        config = Config.get()
        featureDict = Utils.read_features(
            config.get("GeneratedFiles", "zoom_with_id"),
            config.get("GeneratedFiles", "article_coordinates"),
            config.get("GeneratedFiles", "popularity_with_id"),
            config.get("ExternalFiles", "names_with_id"),
            config.get("GeneratedFiles", "percentile_popularity_with_id"),
            required=('x', 'y', 'popularity', 'name', 'maxZoom')
        )

        titlesByZoom = ZoomGeoJSONWriter(featureDict)
        titlesByZoom.generateZoomJSONFeature(config.get("MapData", "title_by_zoom"))


class ZoomGeoJSONWriter:
    def __init__(self, featDict):
        self.articleData = featDict

    def generateZoomJSONFeature(self, filename):
        featureAr = []
        zoomDict = self.articleData
        zoomFeatures = list(zoomDict.values())

        for pointInfo in zoomFeatures:
            pointTuple = (float(pointInfo['x']),float(pointInfo['y']))
            newPoint = Point(pointTuple)
            properties = {'maxzoom':int(pointInfo['maxZoom']), 
                          'popularity':float(pointInfo['popularity']),
                          'citylabel':str(pointInfo['name']),
                          'popbinscore':int(pointInfo['popBinScore'])
                          }
            newFeature = Feature(geometry=newPoint, properties=properties)
            featureAr.append(newFeature)
        collection = FeatureCollection(featureAr)
        textDump = dumps(collection)
        with open(filename, 'w') as writeFile:
            writeFile.write(textDump)

    def writeZoomTSV(self):
        zoomDict = Utils.read_features(config.FILE_NAME_NUMBERED_ZOOM,
                                       config.FILE_NAME_NUMBERED_NAMES)
        #THIS NEEDS TO CHANGE TO BE PART OF THE CONFIG FILE, BUT I'M HARDCODING IT FOR NOW
        filepath = "./web/data/named_zoom.tsv"
        with open(filepath, "a") as writeFile:
            #hardcoded and inelegant, but it works and it's just a data file that only needs to be generated once so...
            writeFile.write('name\tmaxZoom\n')
            for entry in zoomDict:
                name = zoomDict[entry]['name']
                zoom = zoomDict[entry]['maxZoom']
                writeFile.write(name + "\t" + zoom + "\n")
