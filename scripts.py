from pathlib import Path
from gdrive import gdrive
import os 
import ee 
import time
import shutil

from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.pyplot as plt
import rasterio as rio
import numpy as np
import gdal
import gee 

from utils import *

ee.Initialize()

def createPDF(file, df, bands, sources, output):
    
    #get the filename
    filename = Path(file).stem
    
    #extract the bands to use them in names 
    name_bands = '_'.join(bands.split(', '))
    
    #pdf name 
    pdf_file = getResultDir() + '{}_{}.pdf'.format(filename, name_bands)
    
    if os.path.isfile(pdf_file):
        output.add_live_msg('Pdf already exist', 'success')
        return pdf_file
    
    #start the drive handler 
    drive_handler = gdrive()
    
    #create a multipolygon mask 
    ee_multiPolygon = ee.Geometry.MultiPolygon(df['ee_geometry'].tolist()).dissolve(maxError=100)           
            
    
    #create a filename list 
    descriptions = {}
    for year in range(start_year, end_year + 1):
        descriptions[year] = '{}_{}_{}'.format(filename, name_bands, year)
    
    #load all the data in gdrive 
    satellites = {} #contain the names of the used satellites
    for year in range(start_year, end_year + 1):
            
        image, satellites[year] = getImage(sources, bands, ee_multiPolygon, year)
        
        task_config = {
            'image':image,
            'description': descriptions[year],
            'scale': 30,
            'region': ee_multiPolygon,
            'maxPixels': 10e12
        }
            
        task = ee.batch.Export.image.toDrive(**task_config)
        task.start()
        output.add_live_msg('exporting year: {}'.format(year))
    
    #check the exportation evolution 
    task_list = []
    for year in range(start_year, end_year + 1):
        task_list.append(descriptions[year])
            
    state = gee.custom_wait_for_completion(task_list, output)
    output.add_live_msg('Export to drive finished', 'success')
    time.sleep(2)
    
    output.add_live_msg('Retreive to sepal')
    #retreive all the file ids 
    filesId = []
    for year in range(start_year, end_year + 1):
        filesId += drive_handler.get_files(descriptions[year])
    
    #download the files   
    output.add_live_msg('Download files')
    drive_handler.download_files(filesId, getTmpDir())     
    
    #remove the files from gdrive 
    output.add_live_msg('Remove from gdrive')
    drive_handler.delete_files(filesId)            
    
    #create the resulting pdf
    with PdfPages(pdf_file) as pdf:
        #each point is display on one single page
        for index, row in df.iterrows():
            
            page_title = "Polygon_{} ({})".format(
                int(row['id']), 
                row['Name'], 
            )
            
            output.add_live_msg('Creating pages for pt {}'.format(int(row['id'])))
                  
            fig, axes = plt.subplots(nb_line, nb_col, figsize=(11.69,8.27), dpi=500)
            fig.suptitle(page_title, fontsize=16, fontweight ="bold")
            
            #display the images in a fig and export it as a pdf page
            for year in range(start_year, end_year + 1):
                
                #laod the file 
                file = getTmpDir() + descriptions[year] + '.tif'
                
                #create the tmp tif image cuted to buffer size
                tmp_file = getTmpDir() + descriptions[year] + '_pt_{}.tif'.format(row['id'])
                
                #crop the image
                gdal.Warp(tmp_file, file, outputBounds=row['geometry'].bounds)
                
    
                with rio.open(tmp_file) as f:
                    data = f.read([1, 2, 3], masked=True)
                
                bands = [] 
                for i in range(3):
                    band = data[i]
                    h_, bin_ = np.histogram(band[np.isfinite(band)].flatten(), 3000, density=True) #remove the NaN from the analysis
    
                    cdf = h_.cumsum() # cumulative distribution function
                    cdf = 3000 * cdf / cdf[-1] # normalize
    
                    # use linear interpolation of cdf to find new pixel values
                    band_equalized = np.interp(band.flatten(), bin_[:-1], cdf)
                    band_equalized = band_equalized.reshape(band.shape)
        
                    bands.append(band_equalized)
    
                data = np.stack( bands, axis=0 )

                data = data/3000
                data = data.clip(0, 1)
                data = np.transpose(data,[1,2,0])
            
                i = year - start_year
                ax = axes[getPositionPdf(i)[0], getPositionPdf(i)[1]]
                ax.imshow(data, interpolation='nearest')
                ax.set_title(str(year) + ' ' + getShortname(satellites[year]), x=.0, y=.9, fontsize='small', backgroundcolor='white', ha='left')
                ax.axis('off')
                ax.set_aspect('equal', 'box')
            
                #delete the tmp file
                #done on the fly to not exceed sepal memory limits
                os.remove(tmp_file)
            
            
            #finish the line with empty plots 
            start = end_year - start_year
            for i in range(5-(start+1)%5):
                index = start + 1 + i
                ax = axes[getPositionPdf(index)[0], getPositionPdf(index)[1]]
                ax.axis('off')
                ax.set_aspect('equal', 'box')
            
            #save the page 
            plt.tight_layout()
            pdf.savefig(fig)
            plt.close()
            
    #flush the tmp repository 
    shutil.rmtree(getTmpDir())
    
    output.add_live_msg('PDF output finished', 'success')
    
    return pdf_file