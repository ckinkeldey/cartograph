import luigi
import sys

from cartograph import CreateContinents, Coordinates
from cartograph import CreateContours
from cartograph.CalculateZPop import ZPopTask

sys.setrecursionlimit(10000) # 10000 is an example, try with different values

from cartograph import Colors, AllMetrics
# from cartograph.FreeText import FreeTextTask


class ParentTask(luigi.WrapperTask):

    def requires(self):
        return (
            CreateContours(),
            ZPopTask(),
            Coordinates.CreateFullCoordinates(),
            CreateContinents(),
            Colors.ColorsCode(),
            # FreeTextTask(),
            AllMetrics()
        )
