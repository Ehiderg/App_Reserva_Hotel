from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
import pyodbc
import database as db
from datetime import datetime

#template_dir = os.path.dirname(os.path.abspath(os.path.dirname(__file__)))
#template_dir = os.path.join(template_dir, 'src', 'templates')

app = Flask(__name__)

#, template_folder='C:/Users/R3/Desktop/trabajo de DS/Frontend/src'

CORS(app)

# Ruta de inicio de la aplicación
#@app.route('/')
#def home():
 #   return render_template('App.js')

@app.route('/reservar', methods=['POST'])
def reservar():
    data = request.get_json()

    # Extraer información del JSON
    tipo_habitacion = data['tipo_habitacion']
    tipo_cama = data['tipo_cama'] if tipo_habitacion == 'Ordinaria' else 'Sencilla'
    fecha_inicio = datetime.strptime(data['fecha_inicio'], '%Y-%m-%dT%H:%M')
    fecha_fin = datetime.strptime(data['fecha_fin'], '%Y-%m-%dT%H:%M')

    restaurante = data['restaurante']
    transporte = data['transporte']
    parqueadero = data['parqueadero']
    lavanderia = data['lavanderia']
    guia = data['guia']

    # Validar disponibilidad de habitaciones
    habitacion_id = validar_disponibilidad_habitaciones(tipo_habitacion, tipo_cama, fecha_inicio, fecha_fin)
    precio = validar_precio_habitacion(habitacion_id)
    if not habitacion_id:
        return jsonify({'error': 'No hay habitaciones disponibles en las fechas seleccionadas.'}), 400

    # Validar disponibilidad de restaurante
    if restaurante:
        if not validar_disponibilidad_restaurante(fecha_inicio, fecha_fin):
            return jsonify({'error': 'No hay disponibilidad en el restaurante en las fechas seleccionadas.'}), 400

    # Validar disponibilidad de parqueadero
    if parqueadero:
        if not validar_disponibilidad_parqueadero(fecha_inicio, fecha_fin):
            return jsonify({'error': 'No hay disponibilidad en el parqueadero en las fechas seleccionadas.'}), 400

    # Validar paro armado
    if validar_paro_armado(fecha_inicio, fecha_fin):
        return jsonify({'error': 'No se pueden realizar reservas en las fechas seleccionadas debido a un paro armado.'}), 400

    # Crear reserva
    with db.conn.cursor() as cursor:
        try:
            # Insertar reserva y obtener el último ID de identidad insertado
            query_reserva = '''
                INSERT INTO Reserva (nombre_cliente, apellido_cliente, direccion_cliente, habitacion_id, fecha_inicio, fecha_fin, metodo_pago, valor_pago, correo, numero_tarjeta)
                OUTPUT INSERTED.ID_reserva
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            '''
            cursor.execute(query_reserva, data['nombre_cliente'], data['apellido_cliente'], data['direccion_cliente'], habitacion_id, fecha_inicio, fecha_fin, data['metodo_pago'], precio, data['correo'], data['numero_tarjeta'])
            reserva_id = cursor.fetchone()[0]

            # Insertar servicios
            query_servicios = '''
                INSERT INTO Servicios (reserva_id, restaurante, transporte, parqueadero, lavanderia, guia)
                VALUES (?, ?, ?, ?, ?, ?)
            '''
            cursor.execute(query_servicios, reserva_id, data['restaurante'], data['transporte'], data['parqueadero'], data['lavanderia'], data['guia'])

            db.conn.commit()
        except Exception as e:
            # Revertir transacción en caso de error
            cursor.execute("ROLLBACK")
            return jsonify({'error': 'Error al crear la reserva: {}'.format(str(e))}), 500

    return jsonify({'success': 'Reserva realizada con éxito.'}), 200

def validar_precio_habitacion(id):
    with db.conn.cursor() as cursor:
        query = '''
        select h.precio from [dbo].[Habitacion] h
        where h.ID_habitacion = ?
        '''

        cursor.execute(query, id)
        precio = cursor.fetchone()
        
        if precio:
            return precio[0]
        else:
            return None


def validar_disponibilidad_habitaciones(tipo_habitacion, tipo_cama, fecha_inicio, fecha_fin):
    with db.conn.cursor() as cursor:
        query = '''
        SELECT h.ID_habitacion
        FROM Habitacion h
        WHERE h.tipo_habitacion = ? AND h.tipo_cama = ?
            AND (
                (h.tipo_habitacion <> 'Compartida' OR h.tipo_cama <> 'Sencilla')
                OR (h.tipo_habitacion = 'Compartida' AND h.tipo_cama = 'Sencilla' AND (
                    SELECT COUNT(*) FROM Reserva r
                    WHERE r.habitacion_id = h.ID_habitacion AND (
                        (r.fecha_inicio <= ? AND r.fecha_fin >= ?) OR
                        (r.fecha_inicio <= ? AND r.fecha_fin >= ?) OR
                        (r.fecha_inicio >= ? AND r.fecha_fin <= ?)
                    )
                ) < 3)
            )
            AND (
                h.tipo_habitacion <> 'Ordinaria'
                OR (h.tipo_habitacion = 'Ordinaria' AND NOT EXISTS (
                    SELECT 1 FROM Reserva r
                    WHERE r.habitacion_id = h.ID_habitacion AND (
                        (r.fecha_inicio <= ? AND r.fecha_fin >= ?) OR
                        (r.fecha_inicio <= ? AND r.fecha_fin >= ?) OR
                        (r.fecha_inicio >= ? AND r.fecha_fin <= ?)
                    )
                ))
            )
        '''

        cursor.execute(query, tipo_habitacion, tipo_cama, fecha_inicio, fecha_inicio, fecha_fin, fecha_fin, fecha_inicio, fecha_fin,
                       fecha_inicio, fecha_inicio, fecha_fin, fecha_fin, fecha_inicio, fecha_fin)
        habitacion_disponible = cursor.fetchone()
        
        if habitacion_disponible:
            return habitacion_disponible[0]
        else:
            return None


def validar_disponibilidad_restaurante(fecha_inicio, fecha_fin):
    with db.conn.cursor() as cursor:
        query = '''
            SELECT COUNT(*) AS total_reservas
            FROM Reserva r
            WHERE r.fecha_inicio <= ? AND r.fecha_fin >= ?
            AND r.ID_reserva IN (
                SELECT reserva_id
                FROM Servicios
                WHERE restaurante = 1
            )
        '''
        cursor.execute(query, (fecha_fin, fecha_inicio))
        total_reservas = cursor.fetchone()[0]

        return total_reservas <= 40

def validar_disponibilidad_parqueadero(fecha_inicio, fecha_fin):
    with db.conn.cursor() as cursor:
        query = '''
            SELECT COUNT(*) AS total_reservas_parqueadero
            FROM Reserva r
            WHERE r.fecha_inicio <= ? AND r.fecha_fin >= ?
            AND r.ID_reserva IN (
                SELECT reserva_id
                FROM Servicios
                WHERE parqueadero = 1
            )
        '''
        cursor.execute(query, (fecha_fin, fecha_inicio))
        vehiculos_parqueadero = cursor.fetchone()[0]

    return vehiculos_parqueadero <= 25


def validar_paro_armado(fecha_inicio, fecha_fin):
    with db.conn.cursor() as cursor:
        query = '''
            SELECT COUNT(*)
            FROM Paro_Armado p
            WHERE (p.fecha_inicio <= ? AND p.fecha_fin >= ?) OR
                  (p.fecha_inicio <= ? AND p.fecha_fin >= ?) OR
                  (p.fecha_inicio >= ? AND p.fecha_fin <= ?)
        '''
        cursor.execute(query, fecha_inicio, fecha_inicio, fecha_fin, fecha_fin, fecha_inicio, fecha_fin)
        paros_armados = cursor.fetchone()[0]

        return paros_armados > 0

if __name__ == '__main__':
    app.run(debug=True, port=4000)
