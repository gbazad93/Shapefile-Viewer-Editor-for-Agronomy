# Shapefile Viewer and Editor for Agronomy
**This project** is a free, open-source **Python** and **PyQt**-based application designed for agronomists, farmers, and researchers who work with agricultural shapefiles.

It provides a free and user-friendly environment to **open**, **edit**, **analyze**, and **visualize** shapefiles without needing expensive GIS software.

Built with a full graphical interface (frontend) and a powerful geospatial engine (backend), this Editor empowers users to manage agricultural zone maps easily and efficiently.

---

## ✨ Features

- 📂 **Open and Edit Shapefiles (.shp)**
- 🖊️ **Edit, Add, or Delete Attributes and Features**
- 🗺️ **Visualize Zones Over Real-World Satellite Maps**
- 🎨 **Change Zones, Colormaps, and Transparency**
- 🔍 **Zoom and Pan Maps Easily with Sliders and Navigation Buttons**
- 🔎 **Filter and Search Table Data Instantly**
- 📈 **View Quick Statistics About Your Shapefile**
- 📤 **Export Edited Shapefiles Easily**

---

## 🛠️ Built With

- Python
- PyQt6 (for the GUI)
- GeoPandas (for shapefile management)
- Matplotlib (for map plotting)
- Contextily (for adding real-world basemaps)
- Pandas

---

## 📚 Who Is It For?

- Agronomists managing crop zones or soil regions
- Researchers analyzing field boundaries and agricultural zones
- Farmers needing a simple tool to adjust field maps
- GIS enthusiasts looking for an easy, free alternative to edit shapefiles

---

## 📜 License

This project is released as **open-source** so that anyone can use, improve, or contribute to it.

---

# 📦 Installation

This project uses [Pixi](https://prefix.dev/docs/pixi/) for dependency management. If you don’t have Pixi installed:

```bash
curl -sSL https://prefix.dev/install.sh | bash
```

Then, inside the project folder:

```bash
pixi install
pixi run python ShapeFileEditor.py
```

## 🚀 Getting Started

Clone the repository, install the required Python libraries, and run:

```bash
python ShapeFileEditor.py
```

**Requirements:**
- Python 3.x
- geopandas
- matplotlib
- contextily
- PyQt6
- pandas



---

## 💬 Feedback

Feel free to open issues or suggest features if you find something useful to add!  
Let's make agricultural mapping easier for everyone.
