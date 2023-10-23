# AusCal: Australian Event Scheduler

AusCal is a time-management and scheduling calendar service tailored for Australians. Whether you're looking to plan events, get notified about the weather for the day, or integrate with public holiday schedules, AusCal has you covered.

## How It Was Made

AusCal's power comes from its integration with multiple data sources to provide a seamless user experience. 

- **Events Data**: All your events are stored in an SQLite database. This allows for quick retrieval, modifications, and deletions, ensuring your data remains intact and private.
  
- **Weather Data**: AusCal integrates with a free weather API, giving you a forecast for your events up to seven days in advance.

- **Public Holidays**: Using the `au.csv` data file, AusCal knows the public holidays in Australia, ensuring you never mistakenly schedule a major event on a public holiday, unless you want to.

- **Location Intelligence**: With the `georef-australia-state-suburb.csv` file, AusCal is able to understand and interpret Australian suburb and state details. This ensures that you get relevant weather details for your events based on where they're located.

This combination of data sources and smart logic ensures users can schedule and plan their events more efficiently.


## Features
1. **Event Management**: Create, retrieve, update, and delete events seamlessly. Avoid overlaps with built-in overlap detection.
2. **Weather Integration**: Make sure your event's day is bright and sunny or prepare for the occasional shower.
3. **Public Holidays & Weekends**: Schedule your events around public holidays and weekends using our integrated holiday database.
4. **Statistics**: Get a glimpse into your event patterns with our stats feature. How often do you schedule events? When is your busiest month? AusCal will show you.
5. **Visual Data**: Not only can you see event statistics in numbers, but also in visual charts and plots.
6. **Swagger Documentation**: A complete, built-in API documentation system that is easy to navigate.

## Getting Started

### Prerequisites
- Python (3.5 or newer)
- Pip
- Virtualenv

### Built With
- Flask
- Flask-Restx
- SQLite3
- GeoPandas

### Installation

1. Clone this repository:
```bash
git clone git@github.com:jeremytraini/auscal.git
```

2. Move to the project directory and install the required libraries:
```bash
cd auscal
python3 -m venv env
source env/bin/activate
pip3 install -r requirements.txt
```

3. Run the application:
```bash
python3 main.py georef-australia-state-suburb.csv au.csv 
```

4. Open your browser and navigate to:
```
http://localhost:8080/
```

## API Documentation

For detailed API documentation, navigate to the base endpoint after running the application.

## Roadmap

- Integrate with other major Australian data sources.
- Optimise for performance to handle more simultaneous users.
- Develop a dedicated front-end application.

## Contact

- **Email**: hi@jeremytraini.com
