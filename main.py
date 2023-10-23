from io import BytesIO
from flask import Flask, make_response, request
from flask_restx import Api, Namespace, Resource, fields, reqparse

import sqlite3
from matplotlib.dates import DateFormatter
import pandas as pd
import geopandas as gpd
import calendar
from datetime import datetime, timedelta
import sys
import requests
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
# from matplotlib.offsetbox import OffsetImage, AnnotationBbox
# from shapely.geometry import Point, shape
# from PIL import Image

app = Flask(__name__)
api = Api(app,
          default="Events",
          title="AusCal REST API",
          description="A time-management and scheduling calendar service for Australians")

VALID_ORDERS = ['id', 'name', 'datetime']
VALID_FILTERS = ["id", "name", "date", "from", "to", "location"]
DB_NAME = 'events.db'

location_model = api.model('Location', {
    'street': fields.String(required=True, description='Street address'),
    'suburb': fields.String(required=True, description='Suburb'),
    'state': fields.String(required=True, description='State'),
    'post-code': fields.String(required=True, description='Postcode')
})

event_model = api.model('Event', {
    'name': fields.String(required=True, description='Event name', example='my birthday party'),
    'date': fields.String(required=True, description='Event date (format: DD-MM-YYYY)', example='01-01-2024'),
    'from': fields.String(required=True, description='Event start time (format: HH:MM:SS)', example='16:00:00'),
    'to': fields.String(required=True, description='Event end time (format: HH:MM:SS)', example='20:00:00'),
    'location': fields.Nested(location_model, required=True, description='Event location', example={
        'street': '215B Night Ave',
        'suburb': 'Kensington',
        'state' : 'NSW',
        'post-code': '2033'
        }),
    'description': fields.String(required=True, description='Event description', example='some notes on the event')
})

update_location_model = api.model('UpdateLocation', {
    'street': fields.String(required=False, description='Street address'),
    'suburb': fields.String(required=False, description='Suburb'),
    'state': fields.String(required=False, description='State'),
    'post-code': fields.String(required=False, description='Postcode')
})

update_event_model = api.model('UpdateEvent', {
    'name': fields.String(required=False, description='Event name', example='my birthday party'),
    'date': fields.String(required=False, description='Event date (format: DD-MM-YYYY)', example='01-01-2024'),
    'from': fields.String(required=False, description='Event start time (format: HH:MM:SS)', example='16:00:00'),
    'to': fields.String(required=False, description='Event end time (format: HH:MM:SS)', example='20:00:00'),
    'location': fields.Nested(update_location_model, required=False, description='Event location', example={
        'street': '215B Night Ave',
        'suburb': 'Kensington',
        'state' : 'NSW',
        'post-code': '2033'
        }),
    'description': fields.String(required=False, description='Event description', example='some notes on the event')
})

# events_ns = Namespace('Events', description='Event related operations')
# weather_ns = Namespace('Weather', description='Weather related operations')

@api.route('/events', methods=['POST', 'GET'])
class Events(Resource):
    @api.response(200, 'Successful')
    @api.response(400, 'Input Error')
    @api.doc(description="Retrieve the list of available events")
    @api.doc(params={'order': 'Sort order', 'page': 'Page number', 'size': 'Page size', 'filter': 'Filter fields'})
    def get(self):
        # Get query parameters
        order = request.args.get('order', '+id')
        
        try:
            page = int(request.args.get('page', '1'))
        except ValueError:
            return {'message': 'Page is not a number'}, 400
        
        if page < 1:
            return {'message': 'Invalid page number, it must be positive'}, 400
        
        try:
            size = int(request.args.get('size', '10'))
        except ValueError:
            return {'message': 'Page size is not a number'}, 400
        
        if size < 1:
            return {'message': 'Invalid page size, it must be positive'}, 400
        
        filter_str = request.args.get('filter', 'id,name')
        
        # Check if order string is valid
        order_list = list(map(str.strip, order.split(',')))
        order_list_proper = []
        for o in order_list:
            if len(o) < 2:
                return {'message': 'Invalid sort order'}, 400
            
            sort_order = o[0]
            attr = o[1:]
            
            if sort_order not in ['+', '-']:
                return {'message': 'Invalid order'}, 400
            
            if attr not in VALID_ORDERS:
                return {'message': 'Invalid order attribute'}, 400
            
            if attr == 'datetime':
                attr = 'from_date'
            
            order_list_proper.append(
                attr + " " + ("ASC" if sort_order == '+' else "DESC")
            )

        # Check if filter string is valid
        filter_list = list(map(str.strip, filter_str.split(',')))
        sql_filter_list = []
        
        
        
        for f in filter_list:
            if f not in VALID_FILTERS:
                return {'message': 'Invalid filter field, {}'.format(f)}, 400
            else:
                if f == 'date':
                    f = 'from_date'
                elif f == 'from':
                    f = 'from_date'
                elif f == 'to':
                    f = 'to_date'
                elif f == 'location':
                    sql_filter_list.append('street')
                    sql_filter_list.append('suburb')
                    sql_filter_list.append('state')
                    f = 'post_code'
                
                sql_filter_list.append(f)

        if 'location' in filter_list:
            filter_list.remove('location')
            filter_list.append('street')
            filter_list.append('suburb')
            filter_list.append('state')
            filter_list.append('post_code')
        
        # Calculate offset and limit based on page and size
        offset = (page - 1) * size
        next_offset = page * size
        
        limit = size

        # Build SQL query
        query = """
            SELECT {} FROM events ORDER BY {} LIMIT {} OFFSET {}
            """.format(",".join(sql_filter_list), ",".join(order_list_proper), limit, offset)
            
        next_query = """
            SELECT {} FROM events ORDER BY {} LIMIT {} OFFSET {}
            """.format(",".join(sql_filter_list), ",".join(order_list_proper), limit, next_offset)
                
        links = {
            "self": {
                    "href": f"/events?order={order}&page={page}&size={size}&filter={filter_str}"
                }
        }

        # Retrieve events from database
        conn = sqlite3.connect(DB_NAME, detect_types=sqlite3.PARSE_DECLTYPES)
        cursor = conn.cursor()
        cursor.execute(query)
        
        events = []
        for row in cursor.fetchall():
            event_dict = dict(zip(filter_list, row))
            event = {}
            for f in filter_list:
                if f == 'street':
                    event['location'] = {
                        'street': event_dict['street'],
                        'suburb': event_dict['suburb'],
                        'state': event_dict['state'],
                        'post-code': event_dict['post_code']
                    }
                elif f == 'date':
                    event['date'] = event_dict['date'].strftime('%d-%m-%Y')
                elif f == 'from':
                    event['from'] = event_dict['from'].strftime('%H:%M:%S')
                elif f == 'to':
                    event['to'] = event_dict['to'].strftime('%H:%M:%S')
                elif f == 'id':
                    event['id'] = event_dict['id']
                elif f == 'name':
                    event['name'] = event_dict['name']
            
            events.append(event)
        
        cursor.execute(next_query)
        if cursor.fetchone():
            links["next"] = {
                    "href": f"/events?order={order}&page={page+1}&size={size}&filter={filter_str}"
                }
        
        cursor.close()
        conn.close()

        # Build response
        return {
            'page': page,
            'page-size': size,
            'events': events,
            '_links': links
        }, 200
    
    
    @api.doc(description="Add a new event")
    @api.expect(event_model, validate=True)
    def post(self):
        data = request.json
        
        last_update = datetime.now()
        
        try:
            from_date = datetime.strptime(f"{data['date']} {data['from']}", '%d-%m-%Y %H:%M:%S')
            to_date = datetime.strptime(f"{data['date']} {data['to']}", '%d-%m-%Y %H:%M:%S')
        except ValueError:
            return {'message': 'Invalid date or time!'}, 400
        
        if from_date > to_date:
            return {'message': 'From time is after to time!'}, 400

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute("""
                       SELECT * FROM events WHERE from_date < ? AND to_date > ?
                       """, (to_date, from_date))
        
        if cursor.fetchall():
            return {'message': 'The event overlaps with another event.'}, 400

        # Insert the new event into the database
        cursor.execute("""
            INSERT INTO events (name, last_update, from_date, to_date, street, suburb, state, post_code, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (data['name'], last_update, from_date, to_date, data['location']['street'], data['location']['suburb'], data['location']['state'], data['location']['post-code'], data['description']))
        event_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return {
            'id': event_id,
            'last-update': last_update.strftime('%Y-%m-%d %H:%M:%S'),
            '_links': {
                'self': {
                    'href': f'/events/{event_id}'
                }
            }
        }, 201

# Get the weather data of the closest time in the forecast dataseries to the given time range
def get_forecast(data, from_date, to_date):
    init = datetime.strptime(data['init'], '%Y%m%d%H')
    
    from_delta = from_date - init
    from_hours = from_delta.total_seconds() / 3600
    from_index = round(from_hours / 3) - 1
    
    to_delta = to_date - init
    to_hours = to_delta.total_seconds() // 3600
    to_index = round(to_hours / 3) - 1
    
    if from_index < 0 and to_index >= 0:
        # Index 0 must be within the event
        index = 0
    elif from_index >= 0 and from_index < len(data['dataseries']):
        # From index is within the forecast
        index = from_index
    else:
        return None
    
    return data['dataseries'][index]

@api.param('id', 'The event identifier')
@api.response(404, 'Event not found')
@api.response(400, 'Input error')
@api.route('/events/<int:id>', methods=['GET', 'PATCH', 'DELETE'])
class Event(Resource):
    @api.response(200, 'Success')
    @api.doc(description="Retrieve an event by its id")
    def get(self, id):
        if not id or id < 1:
            return {'message': 'Invalid event ID'}, 400
        
        # Retrieve event from database
        conn = sqlite3.connect(DB_NAME, detect_types=sqlite3.PARSE_DECLTYPES)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM events WHERE id = ?
        """, (id,))
        event = cursor.fetchone()
        
        if not event:
            conn.close()
            api.abort(404, "Event {} not found".format(id))
        
        last_update = event[1]
        
        id = event[0]
        name = event[2]
        from_time = event[3]
        to_time = event[4]
        description = event[9]
        
        # Get previous and next event
        cursor.execute("""
                       SELECT id FROM events WHERE from_date < ? ORDER BY from_date DESC LIMIT 1
                       """, (event[3],))
        previous_id = cursor.fetchone()
        
        cursor.execute("""
                       SELECT id FROM events WHERE from_date > ? ORDER BY from_date ASC LIMIT 1
                       """, (event[3],))
        next_id = cursor.fetchone()
        
        conn.close()
        
        location = {
                "street": event[5],
                "suburb": event[6],
                "state": event[7],
                "post-code": event[8]
            }
        
        metadata = {}
        
        # Cleaning state names
        states = {
            "nsw": "new south wales",
            "qld": "queensland",
            "sa": "south australia",
            "tas": "tasmania",
            "vic": "victoria",
            "wa": "western australia",
            "act": "australian capital territory",
            "nt": "northern territory"
        }
        
        state = location["state"].lower()
        suburb = location["suburb"].lower()
        
        if state in states or state in states.values():
            if state in states:
                state = states[state]
            
            df = georef_df
            df = df[df['Official Name State'] == state]
            df = df[df['Official Name Suburb'].str.startswith(suburb)]
            
            if not df.empty:
                lat = df['Geo Point'].str.split(';').str[0].str.split(',').str[0].astype(float).mean()
                lng = df['Geo Point'].str.split(';').str[0].str.split(',').str[1].astype(float).mean()
                
                # Get weather data
                weather_data = requests.get(f'https://www.7timer.info/bin/civil.php?lat={lat}&lng={lng}&ac=1&unit=metric&output=json&product=two').json()
                latest_weather = get_forecast(weather_data, from_time, to_time)
                
                if latest_weather:
                    metadata["wind_speed"] = f"{latest_weather['wind10m']['speed']} KM"
                    metadata["weather"] = latest_weather['weather']
                    metadata["humidity"] = latest_weather['rh2m']
                    metadata["temperature"] = f"{latest_weather['temp2m']} C"
        
        holiday_year = event[3].strftime('%Y')
        holiday_data = requests.get(f'https://date.nager.at/api/v2/publicholidays/{holiday_year}/AU').json()
        
        if isinstance(holiday_data, list):
            holiday_date = event[3].strftime('%Y-%m-%d')
            for holiday_obj in holiday_data:
                if holiday_obj['date'] == holiday_date:
                    metadata["holiday"] = holiday_obj['name']
                    break
        
        metadata["weekend"] = event[3].weekday() >= 5
        
        links = {
            'self': {
                'href': f'/events/{id}'
            }
        }
        
        if previous_id:
            links['previous'] = {
                'href': f'/events/{previous_id[0]}'
            }
            
        if next_id:
            links['next'] = {
                'href': f'/events/{next_id[0]}'
            }
        
        # Return event
        return {
            "id": id,
            "last-update": last_update.strftime('%Y-%m-%d %H:%M:%S'),
            "name": name,
            "date": from_time.strftime('%d-%m-%Y'),
            "from": from_time.strftime('%H:%M:%S'),
            "to": to_time.strftime('%H:%M:%S'),
            "location": location,
            "description": description,
            "_metadata": metadata,
            "_links": links
        }, 200

    @api.response(200, 'Event successfully deleted')
    @api.doc(description="Delete an event")
    def delete(self, id):
        if not id or id < 1:
            return {'message': 'Invalid event ID'}, 400
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute("""
                       SELECT * FROM events WHERE id = ?
                       """, (id,))
        event = cursor.fetchone()
        
        if not event:
            conn.close()
            api.abort(404, "Event {} not found".format(id))
        
        cursor.execute("""
                        DELETE FROM events WHERE id = ?
                        """, (id,))
        conn.commit()
        conn.close()
        
        return {
            "message": f"The event with id {id} was removed from the database!",
            "id": id
        }, 200
    
    @api.doc(description="Update an event")
    @api.expect(update_event_model, validate=True)
    @api.response(200, 'Success')
    def patch(self, id):
        if not id or id < 1:
            return {'message': 'Invalid event ID'}, 400
        
        conn = sqlite3.connect(DB_NAME, detect_types=sqlite3.PARSE_DECLTYPES)
        cursor = conn.cursor()
        
        cursor.execute("""
                       SELECT * FROM events WHERE id = ?
                       """, (id,))
        event = cursor.fetchone()
        
        if not event:
            conn.close()
            api.abort(404, "Event {} not found".format(id))
        
        last_update = datetime.now()
        
        name = event[2]
        from_date = event[3]
        to_date = event[4]
        street = event[5]
        suburb = event[6]
        state = event[7]
        post_code = event[8]
        description = event[9]
        
        for key, value in api.payload.items():
            if key == 'name':
                name = value
            elif key == 'from':
                try:
                    from_date = datetime.strptime(f"{from_date.strftime('%d-%m-%Y')} {value}", '%d-%m-%Y %H:%M:%S')
                except ValueError:
                    return {'message': 'Invalid from time!'}, 400
            elif key == 'to':
                try:
                    to_date = datetime.strptime(f"{to_date.strftime('%d-%m-%Y')} {value}", '%d-%m-%Y %H:%M:%S')
                except ValueError:
                    return {'message': 'Invalid to time!'}, 400
            elif key == 'location':
                for location_key, location_value in value.items():
                    if location_key == 'street':
                        street = location_value
                    elif location_key == 'suburb':
                        suburb = location_value
                    elif location_key == 'state':
                        state = location_value
                    elif location_key == 'post-code':
                        post_code = location_value
            elif key == 'description':
                description = value
        
        if from_date > to_date:
            return {'message': 'From time is after to time!'}, 400
        
        
        cursor.execute("""
                       SELECT * FROM events
                       WHERE from_date < ?
                       AND to_date > ?
                       AND id != ?
                       """, (to_date, from_date, id))
        
        if cursor.fetchall():
            return {'message': 'Invalid time input. The event will overlap with another event.'}, 400
        
        
        cursor.execute("""
                       UPDATE events SET name = ?, last_update = ?, from_date = ?, to_date = ?, street = ?, suburb = ?, state = ?, post_code = ?, description = ? WHERE id = ?
                       """, (name, last_update, from_date, to_date, street, suburb, state, post_code, description, id))
        
        conn.commit()
        
        return {
            "id": id,
            "last-update": last_update.strftime('%Y-%m-%d %H:%M:%S'),
            "_links": {
                "self": {
                    "href": f"/events/{id}"
                }
            }
        }, 200

@api.route('/events/statistics')
class EventsStatistics(Resource):
    @api.doc(description="Get the statistics of the existing events as JSON or image")
    @api.doc(params={'format': 'The format of the response'})
    @api.response(200, 'Successful')
    @api.response(400, 'Invalid format')
    @api.response(404, 'No events to display')
    def get(self):
        if not request.args.get('format'):
            return {'message': 'Missing required parameter: format'}, 400
        
        format_ = request.args.get('format').lower()
        
        conn = sqlite3.connect(DB_NAME, detect_types=sqlite3.PARSE_DECLTYPES)
        cursor = conn.cursor()
        
        if format_ == 'json':
            # Number of events per day
            cursor.execute("""
                            SELECT from_date, count(*) FROM events GROUP BY date(from_date)
                            """)
            per_days = cursor.fetchall()
            
            per_days_dict = {}
            for day in per_days:
                per_days_dict[day[0].strftime('%d-%m-%Y')] = day[1]
            
            # Total Number of events
            cursor.execute("""
                            SELECT count(*) FROM events
                            """)
            total = cursor.fetchone()[0]
            
            today = datetime.now()
            
            end_of_week = today + timedelta(days=6-today.weekday())
            
            cursor.execute("""
                            SELECT count(*) FROM events WHERE from_date >= ? AND from_date <= ?
                            """, (today.replace(hour=0, minute=0, second=0, microsecond=0),
                                  today.replace(month=end_of_week.month,
                                                day=end_of_week.day,
                                                hour=23, minute=59, second=59, microsecond=999999)))
            total_current_week = cursor.fetchone()[0]
            
            cursor.execute("""
                            SELECT count(*) FROM events WHERE from_date >= ? AND from_date <= ?
                            """, (today.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
                                  today.replace(day=calendar.monthrange(today.year, today.month)[1],
                                                hour=23, minute=59, second=59, microsecond=999999)))
            total_current_month = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                "total": total,
                "total-current-week": total_current_week,
                "total-current-month": total_current_month,
                "per-days": per_days_dict
            }, 200
        
        elif format_ == 'image':
            # Number of events per day
            cursor.execute("""
                            SELECT from_date, count(*) FROM events GROUP BY date(from_date)
                            """)
            per_days = cursor.fetchall()
            
            if not per_days:
                return {'message': 'No events to display'}, 404
            
            # Total Number of events
            cursor.execute("""
                            SELECT count(*) FROM events
                            """)
            total = cursor.fetchone()[0]
            
            today = datetime.now()
            
            end_of_week = today + timedelta(days=6-today.weekday())
            
            cursor.execute("""
                            SELECT count(*) FROM events WHERE from_date >= ? AND from_date <= ?
                            """, (today.replace(hour=0, minute=0, second=0, microsecond=0),
                                  today.replace(month=end_of_week.month, day=end_of_week.day, hour=23, minute=59, second=59, microsecond=999999)))
            total_current_week = cursor.fetchone()[0]
            
            cursor.execute("""
                            SELECT count(*) FROM events WHERE from_date >= ? AND from_date <= ?
                            """, (today.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
                                  today.replace(day=calendar.monthrange(today.year, today.month)[1],
                                                         hour=23, minute=59, second=59, microsecond=999999)))
            total_current_month = cursor.fetchone()[0]
            
            conn.close()
            
            plt.close()
            plt.bar([day[0] for day in per_days], [day[1] for day in per_days])
            plt.annotate(f"Total Events: {total}\nTotal Events in the Current Week (Today to Sunday): {total_current_week}\nTotal Events in the Current Month (1st to the last day of the month): {total_current_month}",
                         (0,0), (0, -90), xycoords='axes fraction', textcoords='offset points', va='top')

            # Make y axis integers
            ax = plt.gca()
            ax.yaxis.set_major_locator(MaxNLocator(integer=True))
            
            date_form = DateFormatter("%d/%m/%Y")
            ax.xaxis.set_major_formatter(date_form)
            
            plt.title("Number of Events on each day", pad=15)
            plt.xlabel("Date", labelpad=15)
            plt.ylabel("Number of Events", labelpad=15)
            
            plt.xticks(rotation=45)
            
            plt.tight_layout()
            
            # fig, ax = plt.subplots(figsize=(7, 6))
            
            # # make ax 50% shorter than fig
            # ax.set_position([0.1, 0.1, 0.2, 0.2])
            
            # ax.bar([day[0] for day in per_days], [day[1] for day in per_days], color="blue", align="center")
            
            # # fig.text(-0.5, 0.05, "This is my bottom text", ha='center', fontsize=12)
            # summary_string = f"Total Events: {total}\nTotal Events in the Current Week (Today to Sunday): {total_current_week}\nTotal Events in the Current Month (1st to the last day of the month): {total_current_month}"

            # # ax.annotate(summary_string, xy=(0,0), xytext=(0, -60), xycoords='axes fraction', textcoords='offset points', va='top', annotation_clip=False)
            
            # ax.yaxis.set_major_locator(MaxNLocator(integer=True))
            
            # date_form = DateFormatter("%d/%m/%Y")
            # ax.xaxis.set_major_formatter(date_form)
            
            # ax.set_title("Number of Events on each day", fontweight='bold')
            # ax.set_xlabel(f"""Date
            #               {summary_string}""")
            # ax.set_ylabel("Number of Events")
            
            # fig.autofmt_xdate()
            
            img = BytesIO()
            plt.savefig(img, format='png')
            img.seek(0)

            response = make_response(img)
            response.headers.set('Content-Type', 'image/png')
            return response

            
        else:
            return {'message': 'Invalid format!'}, 400

@api.route('/weather', methods=['GET'])
class Weather(Resource):
    @api.doc(description="Show Australia's weather forecast on a map")
    @api.doc(params={'date': 'Date in the format DD-MM-YYYY'})
    def get(self):
        date = request.args.get('date')
        if date:
            try:
                date = datetime.strptime(date, '%d-%m-%Y')
            except ValueError:
                return {'message': 'Invalid date!'}, 400
        else:
            return {'message': 'Missing required parameter: date'}, 400
            
        today = datetime.now()
            
        # Change time to current time
        date = date.replace(hour=today.hour, minute=today.minute, second=today.second, microsecond=today.microsecond)
        
        ax = georef_df2.plot(color='green')

        # Retrieve weather forecast for each location using the 7timer API
        for _, row in cities_df.iterrows():
            city = row['city']
            lat = row['lat']
            lng = row['lng']
            url = f'https://www.7timer.info/bin/civil.php?lat={lat}&lng={lng}&ac=1&unit=metric&output=json&product=two'
            weather_data = requests.get(url).json()
            weather_at_date = get_forecast(weather_data, date, date)
            
            if not weather_at_date:
                return {'message': 'No weather data found for this date!'}, 404
            
            weather = {
                "city": city,
                "lat": lat,
                "lng": lng,
                "temp": str(weather_at_date['temp2m']),
                "weather": weather_at_date['weather']
            }
            
            weather_str = f'{weather["city"]}\n{weather["temp"]}\N{DEGREE SIGN}C {weather["weather"]}'
            
            lng_adjust = 0
            lat_adjust = 0
            
            if city == 'Adelaide':
                lng_adjust = -1.3
                lat_adjust = 0.5
            elif city == 'Melbourne':
                lat_adjust = -1
            elif city == 'Sydney':
                lng_adjust = 1.2
            
            ax.annotate(weather_str,
                        (row['lng'] + lng_adjust, row['lat'] + lat_adjust),
                        fontsize=10, color='black', ha='center', va='center',
                        bbox=dict(facecolor='white', alpha=0.7, boxstyle='round,pad=0.2', ec='white'))
            
            # Below code is for adding weather icons to the map
            # Could not implement becuase weather-icons folder can't be submitted
            # 
            # image = plt.imread(f'weather-icons/{weather["weather"]}.png')
            # imagebox = OffsetImage(image, zoom=0.2)
            # ab = AnnotationBbox(imagebox, (row['lng']-2, row['lat']+1), frameon=False)
            # ax.add_artist(ab)
        
        ax.set_title('Weather Forecast for ' + date.strftime('%d/%m/%Y'))
        
        
        ax.axis('off')
        fig = ax.get_figure()
        
        img = BytesIO()
        fig.savefig(img, format='png')
        img.seek(0)

        # Return the image as a Flask response
        response = make_response(img)
        response.headers.set('Content-Type', 'image/png')
        return response

# events_ns.add_resource(Events, '')
# events_ns.add_resource(Event, '')
# events_ns.add_resource(EventsStatistics, '')
# weather_ns.add_resource(Weather, '')

# api.add_namespace(weather_ns)
# api.add_namespace(events_ns)

if __name__ == '__main__':
    georef_df = pd.read_csv(sys.argv[1], sep=';')
    
    # Cleaning suburb and state names
    georef_df['Official Name State'] = georef_df['Official Name State'].str.lower()
    georef_df['Official Name Suburb'] = georef_df['Official Name Suburb'].str.lower()
    
    cities_df = pd.read_csv(sys.argv[2])
    cities_df = cities_df[['city', 'lat', 'lng', 'population']]
    
    major_cities = [
        "Sydney",
        "Melbourne",
        "Brisbane",
        "Perth",
        "Adelaide",
        "Hobart",
        "Darwin",
        # "Canberra",
        "Alice Springs",
        "Broome",
        "Cairns"
    ]
    
    cities_df = cities_df[cities_df['city'].isin(major_cities)]
    cities_df['population'] = pd.to_numeric(cities_df['population'])
    cities_df = cities_df[cities_df['population'] >= 10000]
    cities_df = cities_df[['city', 'lat', 'lng', 'population']]
    
    # def eval_point(x):
    #     try:
    #         return shape(eval(x))
    #         # return Point(eval(x))
    #     except:
    #         print(f"Could not evaluate point: {x}")
    #         return None
    # georef_df2 = gpd.read_file(sys.argv[1], delimiter=';', skip_blank_lines=True)
    # georef_df2['geometry'] = georef_df2['Geo Shape'].apply(eval_point)
    
    
    georef_df2 = gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))
    georef_df2 = georef_df2[georef_df2['name'] == 'Australia']
    
    # Setup database
    conn = sqlite3.connect('events.db')
    cursor = conn.cursor()
    # cursor.execute("""
    #     DROP TABLE IF EXISTS events
    #     """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            last_update TIMESTAMP NOT NULL,
            name TEXT NOT NULL,
            from_date TIMESTAMP NOT NULL,
            to_date TIMESTAMP NOT NULL,
            street TEXT NOT NULL,
            suburb TEXT NOT NULL,
            state TEXT NOT NULL,
            post_code TEXT NOT NULL,
            description TEXT
        )
    """)
    
    app.run(debug=True, port=8080)
