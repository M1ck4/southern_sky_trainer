# Southern Sky Trainer

![Southern Sky Trainer Screenshot](doc/screenshot.png)

Southern Sky Trainer is a free and open source desktop application for learning the night sky.

It was created as a practical astronomy learning tool, focused on helping users become more familiar with stars, constellations, deep sky objects, sky position, and celestial coordinates through interactive exploration rather than static reference alone.

This repository contains the public release of that tool.

## Overview

Learning the sky is not only about memorizing names. It is also about recognition, orientation, repeated exposure, and slowly building an internal map of what belongs where. Southern Sky Trainer was built to support that process with a combination of chart-based learning, horizon-based viewing, quizzes, object matching, and coordinate-driven exploration.

The standard chart view is intended as a general learning reference for right ascension and declination. The horizon mode adds a more grounded observational perspective by showing the sky relative to a fixed southern hemisphere observer position. Together, these modes support both abstract coordinate learning and more intuitive visual familiarity.

The application is intended for hobbyists, learners, and anyone who wants a simple desktop tool for developing familiarity with the sky and building confidence with basic astronomical structure.

## Scope

This version of the application is especially suited to southern hemisphere sky learning in its horizon-based mode.

The chart view functions as a general celestial reference for studying right ascension and declination. The horizon-based view is time-aware, but it does not currently detect or adapt to an individual user’s location automatically. Because of that, the horizon experience should be understood as using a fixed southern hemisphere perspective in its current form.

## What the Application Helps You Learn

Southern Sky Trainer is designed to help with several different parts of astronomy learning at once.

It can be used to:

* become familiar with the layout of stars and constellations
* learn how right ascension and declination relate to sky position
* recognize deep sky objects and where they sit relative to brighter stars
* compare abstract chart structure with a horizon-based sky view
* practice identifying objects through repetition and quiz-style interaction
* build intuition about the sky rather than only reading labels from a book or map

## Main Features

* Standard star chart for learning right ascension and declination
* Horizon mode with southern hemisphere sky orientation
* Polar-style sky viewing support
* Constellation support with line relationships
* Deep sky object catalog support
* Quiz and recognition features
* Coordinate and object matching utilities
* Desktop interface built with Python and PySide6
* Data-driven catalogs that can be inspected and expanded

## Viewing Modes

The application includes multiple ways of viewing the sky, each serving a slightly different learning purpose.

### Chart View

The chart view works as a general celestial learning map. It is useful for studying the relationship between stars, constellations, and deep sky objects in terms of right ascension and declination.

This view is especially helpful for:

* learning the coordinate layout of the sky
* understanding where objects sit relative to one another
* building familiarity with the broader structure of the celestial sphere

### Horizon View

The horizon view is designed to represent the sky from an observer-based perspective rather than only as a coordinate chart.

This mode is time-aware and updates according to the current system time, but it uses a fixed southern hemisphere observing perspective in this version of the application. It is therefore most useful for southern sky learning.

This view is especially helpful for:

* translating abstract chart knowledge into a more observational sky perspective
* seeing what appears above the horizon
* building intuition about where objects would sit in a sky-like layout

### Polar View

The polar-style view provides another way to examine sky layout and orientation. It can help reinforce spatial understanding by presenting the sky in a form that differs from the standard chart and horizon views.

## Controls

The application supports mouse-based navigation, keyboard shortcuts, and built-in interface controls.

A summary of the controls is also available from the application's **About** screen.

### Mouse Controls

The main map supports direct mouse interaction for navigation and selection.

* **Scroll wheel**: zoom in and out
* **Drag**: pan the map
* **Double-click**: centre the view on an object
* **Left click**: select an object, or click empty sky for coordinate lookup when using the Identify tool

In horizon view, dragging changes the viewing direction rather than only shifting a flat chart. This makes the horizon mode feel more like looking around the sky from a fixed observing position.

### Keyboard Controls

The application also includes keyboard shortcuts for visibility toggles, navigation, and quiz workflow.

* **1**: toggle stars
* **2**: toggle deep sky objects
* **3**: toggle constellation lines
* **R**: reset the view
* **+ / -**: zoom in and out
* **Arrow keys**: pan the map
* **Ctrl+N**: load a new question
* **Ctrl+A**: show the answer
* **Ctrl+E**: toggle Explore and Quiz mode

In horizon view, the arrow keys rotate the facing direction, and the scroll wheel changes the field of view.

### On-Screen Controls

The interface includes built-in controls for switching between application modes, view modes, and explore tools.

These include:

* Explore and Quiz mode switching
* sky view switching between chart, polar, and horizon views
* explore tool selection for Select, Distance, Path, and Identify
* quiz controls such as New Question, Show Answer, and Reset
* visibility toggles for stars, deep sky objects, and constellation lines

Together these controls make the application useful not only as a viewer, but as an active astronomy learning environment.

## Tools and Learning Utilities

The application is more than a static chart. In explore mode it includes practical tools for inspecting the sky, measuring relationships between objects, and building navigation familiarity.

### Select Tool

The select tool is the simplest inspection mode. It allows the user to click on visible objects and view information about them directly.

This is useful for:

* learning object names through direct interaction
* checking what constellation an object belongs to
* seeing magnitude and object type information
* building familiarity by clicking through the sky rather than only reading a chart

### Distance Tool

The distance tool allows the user to click two objects and measure the angular separation between them.

This makes it useful for:

* understanding how far apart stars or deep sky objects are in angular terms
* comparing sky relationships visually
* learning rough star-hop distances between objects

The star map renders a dashed line between the two selected objects and displays the angular distance directly on the map.

### Path Tool

The path tool allows the user to build a multi-step chain between objects, effectively creating a simple star-hop route across the map.

This is useful for:

* planning or rehearsing a hop between visible targets
* breaking a larger navigation task into smaller steps
* learning object relationships as connected paths instead of isolated points

The map renders numbered stops, dashed connecting segments, and per-leg angular distances, making it a practical learning aid for route-style sky navigation.

### Identify Tool

The identify tool allows the user to click anywhere on the sky rather than only on an existing object.

This supports:

* checking sky position in right ascension and declination
* relating empty sky positions to nearby known objects
* learning how chart coordinates map to practical sky locations

The star map emits sky coordinates for clicked positions specifically to support this style of interaction.

### Quiz Features

The quiz system is designed to reinforce memory through repeated exposure and recall rather than passive viewing alone.

Supported quiz styles include:

* finding a named star
* finding a star by coordinates
* finding a named deep sky object
* finding a deep sky object by coordinates
* finding any named object
* finding any object by coordinates
* finding an object by alias
* finding any object in a named constellation

The quiz engine also includes repeat prevention and spaced repetition behavior for missed objects, helping practice become more structured over time.

### View Controls and Display Toggles

The map itself includes several built-in controls that function as practical learning aids.

These include:

* pan and zoom controls
* click selection and double-click centering
* star visibility toggle
* deep sky visibility toggle
* constellation line toggle
* optional labels and hover information
* time-aware polar and horizon views

These controls matter because they let the user simplify, isolate, and reframe the sky rather than seeing everything at once. The result is a more flexible learning environment.

### Rendering and Visual Learning Support

The map is also designed to communicate information visually, not only textually.

Examples include:

* different symbol shapes for different deep sky object types
* magnitude-based star sizing
* constellation line drawing
* constellation labels
* hover descriptions
* highlighted targets, answers, and selected objects
* a horizon overlay and compass-based horizon grid in horizon mode

These visual cues help turn the application into a practical recognition tool rather than only a data viewer.

## Data Files

A core strength of the project is that key astronomical content is stored in plain data files rather than being hard-coded into the application.

This makes the project easier to inspect, easier to understand, and easier to expand.

### CSV Catalog Files

The CSV files in the `data/` directory can be edited and extended manually.

This means the application can be expanded without major code changes. Users who want to add more entries can do so directly in the catalog files.

Examples include:

* `stars.csv`, for adding or refining star entries
* `deep_sky.csv`, for adding or refining deep sky object entries

If you are comfortable working with CSV files, these catalogs can serve as straightforward, editable data sources for extending the tool.

This is one of the practical strengths of the project. The learning content is not fixed forever. It can grow.

### JSON Configuration Files

The JSON files in the `data/` directory define constellation relationships and supporting structures used by the application.

These include:

* `constellation_lines.json`, which stores line connections used for constellation drawing
* `constellations.json`, which stores constellation-related information used by the program

These files can also be reviewed or modified if constellation content needs refinement or extension.

## Customization

Because the application is partially data-driven, it can be customized in several useful ways without requiring a full redesign.

Possible areas for customization include:

* expanding the star catalog
* expanding the deep sky catalog
* refining constellation line definitions
* adapting the data for alternative learning sets
* using the project as a base for related astronomy learning tools
* modifying quiz behavior or matching logic for your own learning goals

## Repository Structure

A typical repository layout is shown below:

```text
main.py
app_window.py
catalog_loader.py
coordinates.py
object_matcher.py
quiz_engine.py
star_map.py
requirements.txt
README.md
data/
    stars.csv
    deep_sky.csv
    constellation_lines.json
    constellations.json
```

## File Overview

### `main.py`

Application entry point.

### `app_window.py`

Main desktop window and interface-level application behavior.

### `catalog_loader.py`

Loads astronomical catalog and configuration data from the external files in the `data/` directory.

### `coordinates.py`

Contains coordinate-related calculations and supporting astronomical positioning logic.

### `object_matcher.py`

Supports object matching and object lookup style functionality used by the learning tools.

### `quiz_engine.py`

Contains quiz-related logic used for recognition and practice features.

### `star_map.py`

Handles sky rendering, viewing modes, and related display behavior.

## Screenshots

The images below show some of the main ways the application can be used.

### Horizon View with Path Tool

This view shows the southern sky horizon mode with the path tool active, useful for building simple star-hop routes between objects.

![Horizon View with Path Tool](doc/path_view.png)

### Polar View

This view shows the polar-style layout, useful for understanding sky structure from a southern polar perspective.

![Polar View](doc/polar_view.png)

### Quiz Mode

This view shows the application in quiz mode, where the user is asked to identify a target object on the map.

![Quiz Mode](doc/quiz_mode.png)

## Installation

Clone the repository and install the required dependencies:

```bash
pip install -r requirements.txt
```

## Running the Application

Start the program with:

```bash
python main.py
```

## Intended Audience

This project may be useful to:

* learners developing familiarity with the sky
* southern hemisphere hobbyists who want a more relevant horizon-style perspective
* people who want to study right ascension and declination in a practical way
* developers interested in a small open source astronomy project built with Python
* anyone who wants to study the sky through interactive exploration and repetition

## Project Status

This project is released as a working open source tool.

It was originally created for personal use and is being shared publicly in case it is useful to others. It may or may not receive future updates. This repository should be understood as a functional public release rather than a promise of active long-term development.

## License

This project is free and open source.

It is released under the MIT License. See the `LICENSE` file for details..

## Notes

Southern Sky Trainer is best understood as a public release of a practical astronomy learning tool.

It is not presented as a commercial platform or a heavily maintained product. It is a focused educational utility, shared openly because it proved useful in helping build familiarity with the night sky.

It is also intentionally simple in an important way. The catalogs are visible. The data can be edited. The structure can be followed. It is a tool that can be used directly, but it can also be learned from.

## Acknowledgment

Astronomy invites patience, pattern recognition, and perspective. This project was one small way of learning those patterns more directly.

If it helps someone else become more familiar with the sky above them, then it has served its purpose.

---

Made and shared in the spirit of curiosity.
