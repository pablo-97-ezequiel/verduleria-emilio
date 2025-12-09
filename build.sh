#!/bin/bash

# Script de construcción para Render
echo "Instalando dependencias..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Inicializando base de datos..."
python patch.py

echo "Build completado!"
