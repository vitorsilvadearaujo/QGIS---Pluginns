# -*- coding: utf-8 -*-
"""
/***************************************************************************
 OSM2EDGV
                                 A QGIS plugin
 OSM DATA IMPORT TO EDGV DATABASE
                              -------------------
        begin                : 2018-11-24
        git sha              : $Format:%H$
        copyright            : (C) 2018 by Vitor Araujo
        email                : vitorsilvadearaujo@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from PyQt4.QtCore import QSettings, QTranslator, qVersion, QCoreApplication
from PyQt4 import QtGui
from PyQt4.QtGui import QAction, QIcon,QFileDialog
from processing import *
# Initialize Qt resources from file resources.py
import resources
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
# Import the code for the dialog
from  OSM2EDGV_dialog import  OSM2EDGVDialog
import os.path
import psycopg2
from PyQt4.QtGui import QAction, QIcon
from qgis.core import QgsMapLayer
from qgis.core import QgsFeature, QgsGeometry
from qgis.core import QgsVectorLayer
from qgis.core import QgsDataSourceURI
from qgis.gui import *
import sys
import processing
import numpy as np
import sqlite3
import string
import csv


class OSM2EDGV:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'OSM2EDGV_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)


        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&OSM2EDGV')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'OSM2EDGV')
        self.toolbar.setObjectName(u'OSM2EDGV')
        self.dlg = OSM2EDGVDialog()
        self.list = QListWidget()
    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('OSM2EDGV', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        # Create the dialog (after translation) and keep reference


        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/OSM2EDGV/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'OSM2EDGV'),
            callback=self.run,
            parent=self.iface.mainWindow())
        self.dlg.compati.clicked.connect(self.run)


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&OSM2EDGV'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar


    def run(self):
        """Run method that performs all the real work"""
        layers = self.iface.legendInterface().layers()
        layer_list = []
        for layer in layers:
            layer_list.append(layer.name())
        self.dlg.comboBox.addItems(layer_list)
        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
#DADOS DE ENTRADA PARA CONEXAO
            database = self.dlg.database.text()
            servidor = self.dlg.servidor.text()
            user = self.dlg.user.text()
            senha = self.dlg.senha.text()
            uri = QgsDataSourceURI()
#CONEXAO A TRAVEZ DO PSYCOPG2
            conn= psycopg2.connect(database=database, host=servidor, user = user, password=senha, port = "5432" )
#CRIACAO DE UM CURSOR PARA TESTE DE CONEXAO
            cur = conn.cursor()
            test = cur.closed
#TESTE DE CONEXAO
            if test == False:

                QMessageBox.information(self.iface.mainWindow(),"Info","Importing...")
            elif test == True:
                QMessageBox.information(self.iface.mainWindow(),"Info","Dados de conexao invalidos")
            layerindex = self.dlg.comboBox.currentIndex()
            selectedLayer = layers[layerindex]
            fields = selectedLayer.pendingFields()
            field_names = [field.name() for field in fields]
            features = selectedLayer.getFeatures()
            geo_lista=[]
            i=1
            for feature in selectedLayer.getFeatures():
                geom = feature.geometry()

#TESTE DE PRIMITIVA GRÁFICA - LINHA
                if geom.type() == 1:
                    conn= psycopg2.connect(database=database, host=servidor, user = user, password=senha, port = "5432" )
                    cur = conn.cursor()
#VERIFICANDO EXISTÊCIA DE TABELASS DE REGRAS para ARRUAMENTO				
                    cur.execute("select exists(SELECT * FROM information_schema.tables where table_name='arruamento')")
                    verifica = cur.fetchone()[0]
                    conn.commit() 
                    
                    if verifica == False:
#IMPORTANDO TABLEAS PARA O BANCO DE DADOS
                        conn= psycopg2.connect(database=database, host=servidor, user = user, password=senha, port = "5432" )
                        cur = conn.cursor()
                        cur.execute("""CREATE TABLE arruamento(tag text,classe text,key text,value text)""")
                        with open(r'/home/user/.qgis2/python/plugins/OSM2EDGV/arruam.csv', 'r') as f:
                            reader= csv.reader(f, delimiter=';')
                            next(reader)  # Skip the header row.
                            for row in reader:

                                cur.execute("""INSERT INTO arruamento (tag , classe , key , value) VALUES (%s, %s, %s, %s)""", row)
                            conn.commit()
                    conn.close()
                    conn= psycopg2.connect(database=database, host=servidor, user = user, password=senha, port = "5432" )
                    cur = conn.cursor()
                    cur.execute("select exists(SELECT * FROM information_schema.tables where table_name='revest')")
                    verifica2 = cur.fetchone()[0]

                    conn.commit() 
                    
                    if verifica2 == False:
                        conn= psycopg2.connect(database=database, host=servidor, user = user, password=senha, port = "5432" )
                        cur = conn.cursor()

                        cur.execute("""CREATE TABLE revest(tipo text,revestimento text)""")
                        with open(r'/home/user/.qgis2/python/plugins/OSM2EDGV/revest.csv', 'r') as f:
                            reader = csv.reader(f, delimiter=';')
                            next(reader)  # Skip the header row.
                            for row in reader:
                                cur.execute("""INSERT INTO revest (tipo , revestimento) VALUES (%s, %s)""", row)
                            conn.commit()

                    tag1=feature["highway"]
    
                    if type(tag1)  is not QPyNullVariant:
                        cur.execute("""SELECT * FROM arruamento WHERE tag='%s' """ % tag1)
                        select1=cur.fetchone()

                        if select1 is not None:
                            tag=select1[0]
                            classe=select1[1]
                            key= select1[2]
                            value=select1[3]
                            position1= field_names.index('name')
                            nome_rua=feature[position1]
                            if type(nome_rua) is unicode:
                                nome_rua=string.replace(nome_rua,"'","")
                                nome_rua = nome_rua.encode('ascii', 'ignore').decode('ascii')
                            else:
                                nome_rua='NULL'
                
                            if classe != 'cb_trecho_arruamento_l':
                                
                                geom = feature.geometry()
                                geo_lista=[(geom.exportToWkt())]
                                for g in geo_lista:
                                    if key == 'revestimento':
                                        value1= field_names.index('surface')
                                        cur.execute("""SELECT * FROM revest WHERE tipo='%s' """ % value1)
                                        select4=cur.fetchone()
                                        if select4 is not None:
                                            value=select4[1]
                                        if value== '4':
                                            value='3'
                                        if value== '95':
                                            value='3'
                                    cur.execute("select exists ( SELECT * FROM information_schema.columns WHERE table_name='%s' AND column_name='id_osm')"%(classe))
                                    verifica1 = cur.fetchone()[0]
                                    cur.execute("select exists ( SELECT * FROM information_schema.columns WHERE table_name='%s' AND column_name='dia')"%(classe))
                                    verifica2 = cur.fetchone()[0]
                                    if (verifica1 == False ) or (verifica2 == False ):
                                        cur.execute(""" ALTER TABLE %s ADD COLUMN id_osm text; """ %(classe))
                                        cur.execute(""" ALTER TABLE %s ADD COLUMN dia date; """ %(classe))
                                        cur.execute(""" INSERT INTO %s (id, nome,%s,geom,id_osm,dia) VALUES (%s,  '%s' , CAST (%s AS SMALLINT),ST_Multi(ST_GeomFromText( '%s',4674)), %s, NOW()) """ %(classe,key,i,nome_rua,value,g,i))
                                    else:
                                        cur.execute(""" INSERT INTO %s (id, nome,%s,geom,id_osm,dia) VALUES (%s,  '%s' , CAST (%s AS SMALLINT),ST_Multi(ST_GeomFromText( '%s',4674)), %s, NOW()) """ %(classe,key,i,nome_rua,value,g,i))
                                    i=i+1;
                                    conn.commit() 
                            if classe == 'cb_trecho_arruamento_l':
                                position3= field_names.index('surface')
                                revestimento = (feature[position3])

                                if type(feature[position3]) is not QPyNullVariant:
                                    cur.execute("""SELECT * FROM revest WHERE tipo='%s' """ % feature[position3])
                                    select2=cur.fetchone()
                                if select2 is not None:
                                    revest=select2[1]
                                if revest== '4':
                                    revest='95'
    
                                position4= field_names.index('lanes')
                                if type(feature[position4]) is not  QPyNullVariant:
                                    faixas = (feature[position4])
                
                                geom = feature.geometry()
                                geo_lista=[(geom.exportToWkt())]
                                for g in geo_lista:
                                        cur.execute("select exists ( SELECT * FROM information_schema.columns WHERE table_name='%s' AND column_name='id_osm')"%(classe))
                                        verifica1 = cur.fetchone()[0]
                                        cur.execute("select exists ( SELECT * FROM information_schema.columns WHERE table_name='%s' AND column_name='dia')"%(classe))
                                        verifica2 = cur.fetchone()[0]
                                        if (verifica1 == False ) or (verifica2 == False ):
                                            cur.execute(""" ALTER TABLE %s ADD COLUMN id_osm text; """ %(classe))
                                            cur.execute(""" ALTER TABLE %s ADD COLUMN dia date; """ %(classe))
                                            cur.execute(""" INSERT INTO %s (id, nome,%s,geom,id_osm,dia) VALUES (%s,  '%s' , CAST (%s AS SMALLINT),ST_Multi(ST_GeomFromText( '%s',4674)), %s, NOW()) """ %(classe,key,i,nome_rua,value,g,i))
                                        else:
                                            cur.execute(""" INSERT INTO %s (id, nome,%s,geom,id_osm,dia) VALUES (%s,  '%s' , CAST (%s AS SMALLINT),ST_Multi(ST_GeomFromText( '%s',4674)), %s, NOW()) """ %(classe,key,i,nome_rua,value,g,i))
                                        i=i+1;
                                        conn.commit() 
                                conn.close()

                    port = "5432"
                    uri = QgsDataSourceURI()            
                    uri.setConnection(servidor,port , database, user, senha)
                    uri.setDataSource("ge", "cb_trecho_arruamento_l", "geom")
                    layer1 = QgsVectorLayer(uri.uri(),"Trecho_Arruamento","postgres")
                    QgsMapLayerRegistry.instance().addMapLayer(layer1)
                    layer1.loadNamedStyle('/home/user/.qgis2/python/plugins/OSM2EDGV/estilos/Arruamento.qml')

                    uri.setDataSource("ge", "emu_ciclovia_l", "geom")
                    layer2 = QgsVectorLayer(uri.uri(),"Ciclovia","postgres")
                    QgsMapLayerRegistry.instance().addMapLayer(layer2)
                    layer2.loadNamedStyle('/home/user/.qgis2/python/plugins/OSM2EDGV/estilos/Ciclovia.qml')

                    uri.setDataSource("ge", "emu_escadaria_l", "geom")
                    layer3 = QgsVectorLayer(uri.uri(),"Escadarias","postgres")
                    QgsMapLayerRegistry.instance().addMapLayer(layer3)
                    layer3.loadNamedStyle('/home/user/.qgis2/python/plugins/OSM2EDGV/estilos/Escadarias.qml')

                    uri.setDataSource("ge", "emu_acesso_l", "geom")
                    layer4 = QgsVectorLayer(uri.uri(),"Acessos","postgres")
                    QgsMapLayerRegistry.instance().addMapLayer(layer4)
                    layer4.loadNamedStyle('/home/user/.qgis2/python/plugins/OSM2EDGV/estilos/Acesso.qml')

                    uri.setDataSource("pe", "tra_trilha_picada_l", "geom")
                    layer5 = QgsVectorLayer(uri.uri(),"Trilhas e Picadas","postgres")
                    QgsMapLayerRegistry.instance().addMapLayer(layer5)
                    layer5.loadNamedStyle('/home/user/.qgis2/python/plugins/OSM2EDGV/estilos/Trilha.qml')

					
					
					
					
					
#POLIGONOS#
                
                if geom.type() == 2:
#VERIFICANDO EXISTÊCIA DE TABELASS DE REGRAS para EDIFICACOES
                    conn= psycopg2.connect(database=database, host=servidor, user = user, password=senha, port = "5432" )
                    cur = conn.cursor()
                    cur.execute("select exists(SELECT * FROM information_schema.tables where table_name='edif')")
                    verifica = cur.fetchone()[0]
                    conn.commit() 
                    if verifica == False:
#IMPORTANDO TABLEAS PARA O BANCO DE DADOS
                        conn= psycopg2.connect(database=database, host=servidor, user = user, password=senha, port = "5432" )
                        cur = conn.cursor()
                        cur.execute("""CREATE TABLE edif(tag text,classe text)""")
                        with open(r'/home/user/.qgis2/python/plugins/OSM2EDGV/edif.csv', 'r') as f:
                            reader= csv.reader(f, delimiter=';')
                            next(reader)  # Skip the header row.
                            for row in reader:

                                cur.execute("""INSERT INTO edif(tag , classe ) VALUES (%s, %s)""", row)
                            conn.commit()
                    conn.close()

                    tag1=feature["building"]


                    if type(tag1)  is not QPyNullVariant:
                        conn= psycopg2.connect(database=database, host=servidor, user = user, password=senha, port = "5432" )
                        cur = conn.cursor()
                        cur.execute("""SELECT * FROM edif WHERE tag='%s' """ % tag1)
                        select1=cur.fetchone()
                        position1= field_names.index('name')
                        nome=feature[position1]
                        if type(nome) is unicode:
                            nome=string.replace(nome,"'","")
                            nome= nome.encode('ascii', 'ignore').decode('ascii')
                        else:
                            nome='NULL'
                        if select1 is not None:
                            tag=select1[0]
                            classe=select1[1]
                            geom = feature.geometry()
                            geo_lista=[(geom.exportToWkt())]
                            for g in geo_lista:
                                id_osm=feature["id"]
                                cur.execute("select exists ( SELECT * FROM information_schema.columns WHERE table_name='%s' AND column_name='id_osm')"%(classe))
                                verifica1 = cur.fetchone()[0]
                                cur.execute("select exists ( SELECT * FROM information_schema.columns WHERE table_name='%s' AND column_name='dia')"%(classe))
                                verifica2 = cur.fetchone()[0]
                                if (verifica1 == False ) or (verifica2 == False ):
                                    cur.execute(""" ALTER TABLE %s ADD COLUMN id_osm text; """ %(classe))
                                    cur.execute(""" ALTER TABLE %s ADD COLUMN dia date; """ %(classe))
                                    cur.execute(""" INSERT INTO %s (id,nome,geom,id_osm,dia) VALUES (%s,  '%s' , ST_Multi(ST_GeomFromText( '%s',4674)), %s, NOW()) """ %(classe,i,nome,g,id_osm))
                                else:
                                    cur.execute(""" INSERT INTO %s (id,nome,geom,id_osm,dia) VALUES (%s,  '%s' , ST_Multi(ST_GeomFromText( '%s',4674)), %s, NOW()) """ %(classe,i,nome,g,id_osm))
                                    
                                i=i+1
                                conn.commit() 
                    conn.close()
                
                    port = "5432"
                    uri = QgsDataSourceURI()
                    uri.setConnection(servidor,port , database, user, senha)
                    uri.setDataSource("ge", "edf_edif_residencial_a", "geom")
                    layer1 = QgsVectorLayer(uri.uri(),"Edif_Residenciais","postgres")
                    QgsMapLayerRegistry.instance().addMapLayer(layer1)
                    layer1.loadNamedStyle('/home/user/.qgis2/python/plugins/OSM2EDGV/estilos/Edifica.qml')

                    uri.setDataSource("ge", "edf_edif_comerc_serv_a", "geom")
                    layer2 = QgsVectorLayer(uri.uri(),"Edif_Comerciais","postgres")
                    QgsMapLayerRegistry.instance().addMapLayer(layer2)
                    layer2.loadNamedStyle('/home/user/.qgis2/python/plugins/OSM2EDGV/estilos/Edifica_Outras.qml')

                    uri.setDataSource("ge", "edf_edif_ensino_a", "geom")
                    layer3 = QgsVectorLayer(uri.uri(),"Edif_Ensino","postgres")
                    QgsMapLayerRegistry.instance().addMapLayer(layer3)
                    layer3.loadNamedStyle('/home/user/.qgis2/python/plugins/OSM2EDGV/estilos/Edifica.qml')

                    uri.setDataSource("ge", "edf_edif_religiosa_a", "geom")
                    layer4 = QgsVectorLayer(uri.uri(),"Edif_Religiosa","postgres")
                    QgsMapLayerRegistry.instance().addMapLayer(layer4)
                    layer4.loadNamedStyle('/home/user/.qgis2/python/plugins/OSM2EDGV/estilos/Edifica.qml')

                    uri.setDataSource("pe", "edf_edif_saude_a", "geom")
                    layer5 = QgsVectorLayer(uri.uri(),"Edif_Saude","postgres")
                    QgsMapLayerRegistry.instance().addMapLayer(layer5)
                    layer5.loadNamedStyle('/home/user/.qgis2/python/plugins/OSM2EDGV/estilos/Edifica.qml')

                    uri.setDataSource("pe", "cb_estacionamento_a", "geom")
                    layer6 = QgsVectorLayer(uri.uri(),"Estacionamentos","postgres")
                    QgsMapLayerRegistry.instance().addMapLayer(layer6)
                    layer6.loadNamedStyle('/home/user/.qgis2/python/plugins/OSM2EDGV/estilos/Edifica_Outras.qml')

                    uri.setDataSource("pe", "edf_edif_industrial_a", "geom")
                    layer7 = QgsVectorLayer(uri.uri(),"Edif_Industrial","postgres")
                    QgsMapLayerRegistry.instance().addMapLayer(layer7)
                    layer7.loadNamedStyle('/home/user/.qgis2/python/plugins/OSM2EDGV/estilos/Edifica_Industr.qml')

                    uri.setDataSource("pe", "eco_deposito_geral_a", "geom")
                    layer8 = QgsVectorLayer(uri.uri(),"Edif_Industrial","postgres")
                    QgsMapLayerRegistry.instance().addMapLayer(layer8)
                    layer8.loadNamedStyle('/home/user/.qgis2/python/plugins/OSM2EDGV/estilos/Edifica_Industr.qml')