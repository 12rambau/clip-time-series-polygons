# clip-time-series-polygons

create a clip time series for a list of polygons

![clip](./img/clip.png)


## Usage

first download the repository to your own sepal account 

```
git clone https://github.com/12rambau/clip-time-series-polygons.git
```

In the `clip-time-series-polygons` folder, copy paste the `parameters.py.dist` file and remove the `.dist` extention 

```
cp parameters.py.dist parameters.py
```

You'll need to change the values of the parameters according to your needs. 
- polygon_file : name of the file conatining the polygon list
- bands_combo: bands combo you want to display (the available list of combo is written in the parmaeters file)
- nb_squares: number of squares to display on the map to verify there size and shapes
- polygon_color: the color wich will be used for the display of the polygon
- test_mode: set if you're in test mode where you will only take into account the first 2 polygons of your list

Then in the `clip-time-series-polygons` folder, launch the `clip.ipynb` notebook and run its cells. 
