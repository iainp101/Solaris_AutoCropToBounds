# Solaris_AutoCropToBounds
Automatically crops the render region to the bounding box of the selected object(s) in Houdini Solaris.

## Background
I've found on several shows, including my most recent, that when rendering assets to separate passes - some shots have a lot of empty space surrounding the object. Cropping the render region helped reduce render times and reduce memory usage. I wanted a way, in Solaris, to automatically crop the render region to the asset to make pass setup quicker and negate the need to either set a much larger crop to account for the animation path and/or exporting a mask sequence from Nuke and having to update it each time the animation changed.

## Setup
At the moment, I have the python code in a Python LOP node with some additional parameters added for easier control. You will also need a cache node to look backwards and forwards to account for motion blur. Please see the example .hip file.

AutoCropToBounds will either have to be placed after any Render Settings node, or for the dataWindowNDC parameter to be disabled in order for AutoCropToBounds to be the last LOP to be setting the dataWindowNDC value. This script will respect any previously set values should the asset reach the edge of the frame, such as overscan.
