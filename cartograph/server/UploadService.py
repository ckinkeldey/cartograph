import json

import numpy as np
import os
import pandas as pd
import shutil

from AddMapService import check_map_name


class UploadService:
    def __init__(self, map_services, upload_dir):
        """
        Creates a new service to handle data uploads.
        Args:
            map_services: Dictionary from map name to map
            upload_dir: Absolute full path to map directory
        """
        self.map_services = map_services
        self.upload_dir = upload_dir

        if not os.path.isdir(self.upload_dir):
            os.makedirs(self.upload_dir)

    def on_post(self, req, resp):
        resp.body = ''

        # Check the map name and make sure the dest file is empty
        map_name = req.get_param('map_name')
        try:
            check_map_name(map_name, self.map_services)
        except ValueError as e:
            resp.body = json.dumps({
                'success': False,
                'map_name': map_name,
                'error': str(e),
                'stacktrace': repr(e),
            })
            return

        # If file exists remove it
        dest = self.upload_dir + '/' + map_name + '.tsv'
        if os.path.isfile(dest):
            os.unlink(dest)

        # Write the supplied text or file to a temporary tsv
        articles_file = req.get_param('file')
        articles_text = req.get_param('file_text')
        if articles_file not in (None, ''):
            with open(dest, 'wb') as f:
                shutil.copyfileobj(articles_file.file, f)
        elif articles_text not in (None, ''):
            with open(dest, 'wb') as f:
                f.write(articles_text)
                f.close()
        else:
            raise ValueError, "Missing article both text and upload file"

        # Scan the TSV for field names.
        # TODO: This should handle lots of things:
        # - Different encodings
        # - Files that are too long
        # - Files that are irregularly formatted (be gentle with errors)
        try:
            df = pd.read_csv(dest, sep='\t')
            nrows, ncols = df.shape
            cols = df.columns.tolist()
            assert (len(cols) == ncols)

            # # Detect types of data
            # types = []
            # for dt in list(df.dtypes):
            #     if dt in (np.str, np.object):
            #         types.append('string')
            #     elif dt == np.int64:
            #         types.append('int')
            #     elif dt == np.float64:
            #         types.append('float')
            #     else:
            #         raise ValueError('unknown type: ' + str(dt))

            # Explicitly set first column
            cols[0] = 'title'
            # types[0] = 'string'
            types = ['string']
            types.extend(self.detectDataTypes(df))  # Not set types for first column
            numClasses = self.qualitativeNumClasses(df)  # Number of data classes for qualitative columns

            resp.body = json.dumps({
                'success': True,
                'map_name': map_name,
                'columns': cols,
                'types': types,
                'num_rows': nrows,
                'num_classes': numClasses,
            })
        except ValueError as e1:
            resp.body = json.dumps({
                'success': False,
                'map_name': map_name,
                'error': str(e1),
                'stacktrace': repr(e1),
            })

        except TypeError as e2:
            resp.body = json.dumps({
                'success': False,
                'map_name': map_name,
                'error': str(e2),
                'stacktrace': repr(e2),
            })

    def detectDataTypes(self, df):
        # TODO: Make valid columns available, hide invalid columns
        types = []
        for col in df.columns[1:]:
            dt = df[col].dtype
            type = {'sequential': False, 'diverging': False, 'qualitative': False}
            if dt in (np.str, np.object):
                numUnique = len(df[col].unique())
                if numUnique <= 9:
                    type['qualitative'] = True
                    types.append(type)
                else:
                    # types.append(None)
                    raise ValueError('too many classes for qualitative data: ' + str(numUnique))
            elif dt in (np.int64, np.float64):
                type['sequential'] = True
                type['diverging'] = True
                if len(df[col].unique()) <= 12:
                    type['qualitative'] = True
                types.append(type)
            else:
                raise ValueError('unknown type: ' + str(dt))

        return types

    def qualitativeNumClasses(self, df):
        # Find number of data classes for qualitative columns. Return None for sequential and diverging ones.
        numClasses = []
        for col in df.columns[1:]:
            numClasses.append(len(df[col].unique()) if len(df[col].unique()) <= 12 else None)
        return numClasses
