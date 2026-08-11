#!/usr/bin/env pymol
cmd.load("sup", "structure1")
cmd.load("4jhm.pdb1", "structure2")
hide all
set all_states, on
show ribbon, structure1
show ribbon, structure2
color blue, structure1
color red, structure2
set ribbon_width, 6
set stick_radius, 0.3
set sphere_scale, 0.25
set ray_shadow, 0
bg_color white
set transparency=0.2
zoom polymer and ((structure1) or (structure2))

