from pathlib import Path
import ee 
from datetime import datetime as dt
from urllib.request import urlretrieve
import zipfile

from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.pyplot as plt
import rasterio as rio
import numpy as np
import gdal

from utils import *
from parameters import *

ee.Initialize()

def createPDF(file, df, raw_polygons, bands, sources, output):
    
    start = dt.now().replace(microsecond=0)
    
    # get the filename
    filename = Path(file).stem
    
    # extract the bands to use them in names 
    name_bands = '_'.join(bands.split(', '))
    
    # pdf file 
    pdf_file = result_dir/f'{filename}_{name_bands}.pdf'
    
    if pdf_file.is_file():
        output.add_live_msg('Pdf already exist', 'success')
        return pdf_file
    
    # create a filename list 
    descriptions = {}
    for year in range(start_year, end_year + 1):
        descriptions[year] = {}
        for index, row in df.iterrows():
            descriptions[year][row['id']] = f'{filename}_{name_bands}_{year}_pt_{row.id}'
    
    # load all the data in gdrive 
    satellites = {} # contain the names of the used satellites
    task_list = []
    for year in range(start_year, end_year + 1):
        for index, row in df.iterrows():
        
            # launch it only if the file is not in tmp, or in gdrive
            task_name = descriptions[year][row['id']]
            dst = tmp_dir/f'{task_name}.tif'
            
            image, satellites[year] = getImage(sources, bands, row['ee_geometry'], year)
            
            output.add_msg('exporting year {} for point {}'.format(year, row['id']))
            
            if not dst.is_file():
                
                name = f'{task_name}_zipimage'
                
                link = image.getDownloadURL({
                    'name': name,
                    'region': row.ee_geometry,
                    'filePerBand': False,
                    'scale': getScale(satellites[year])
                })
                
                tmp = tmp_dir/f'{name}.zip'
                urlretrieve (link, tmp)
                
                # unzip the file 
                with zipfile.ZipFile(tmp,"r") as zip_:
                    data = zip_.read(zip_.namelist()[0])
                    
                dst.write_bytes(data)
                
                # remove the zip 
                tmp.unlink()           
    
    # create the resulting pdf
    with PdfPages(pdf_file) as pdf:
        # each point is display on one single page
        for index, row in df.iterrows():
            
            page_title = f'Polygon_{row.id} ({row.name})'
            
            output.add_msg(f'Creating pages for pt {row.id}')
            
            nb_col, nb_line = get_dims(end_year-start_year)
                  
            fig, axes = plt.subplots(nb_line, nb_col, figsize=(11.69,8.27), dpi=500)
            fig.suptitle(page_title, fontsize=16, fontweight ="bold")
            
            # display the images in a fig and export it as a pdf page
            cpt = 0
            for year in range(start_year, end_year + 1):
                
                # laod the file 
                file = tmp_dir/f'{descriptions[year][row.id]}.tif'                
    
                with rio.open(file) as f:
                    data = f.read([1, 2, 3], masked=True)
                    x_min, y_min, x_max, y_max = list(f.bounds)
                
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
            
                x_polygon, y_polygon = raw_polygons.loc[index]['geometry'].exterior.coords.xy
            
                ax = axes[getPositionPdf(cpt, nb_col)[0], getPositionPdf(cpt, nb_col)[1]]
                ax.imshow(data, interpolation='nearest', extent=[x_min, x_max, y_min, y_max])
                ax.plot(x_polygon, y_polygon, color=polygon_color, linewidth=polygon_width)
                ax.set_title(f'{year} {getShortname(satellites[year])}', x=.0, y=.9, fontsize='small', backgroundcolor='white', ha='left')
                ax.axis('off')
                ax.set_aspect('equal', 'box') 
                
                cpt += 1
                
                # remove the file 
                file.unlink()
            
            # finish the line with empty plots 
            while cpt < nb_line*nb_col:
                ax = axes[getPositionPdf(cpt, nb_col)[0], getPositionPdf(cpt, nb_col)[1]]
                ax.axis('off')
                ax.set_aspect('equal', 'box')
                
                cpt += 1
            
            # save the page 
            plt.tight_layout()
            pdf.savefig(fig)
            plt.close()
    
    elapsed_time = dt.now().replace(microsecond=0)-start
    output.add_live_msg(f'PDF output finished in {elapsed_time}', 'success')
    
    return pdf_file