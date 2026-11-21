# A seashell: a parametric surface, lit, in a sunset palette.
# In puritty, or another terminal that shows Kitty's graphics:
#
#     gnuplot seashell.gp
#
# The picture is drawn where the cursor is, under the command.

# The size in pixels (make it fit your window) and the background
# (puritty's dark one here; leave it out for white).
set term kittycairo scroll size 1200,600 \
    background rgb '#282c34'
# A gnuplot built without cairo has no kittycairo: Sixel instead.
# set term sixelgd truecolor scroll size 1200,600 \
#     background rgb '#282c34'

set parametric
set urange [0:6*pi]
set vrange [0:2*pi]
set isosamples 180,72
unset border; unset tics; unset key; unset colorbox
set view 72,128,1.35,1.1

# depthorder draws the far side first; the lighting gives it a shine
set pm3d depthorder noborder \
    lighting primary 0.55 specular 0.35 spec2 0.15
set palette defined (0 '#1a1b4b', 0.35 '#6b2f8e', \
    0.6 '#d9566b', 0.8 '#f28f3b', 1 '#f2e863')

# u winds the shell around its axis three times;
# v goes round the tube
e(u) = exp(u/(6*pi))
x(u,v) = 2*(1-e(u))*cos(u)*cos(v/2)**2
y(u,v) = 2*(e(u)-1)*sin(u)*cos(v/2)**2
z(u,v) = 1-exp(u/(3*pi))-sin(v)+e(u)*sin(v)

splot x(u,v), y(u,v), z(u,v) with pm3d
