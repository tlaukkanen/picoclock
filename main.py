"""
Raspberry Pico W clock with weather and electricity price display
https://github.com/tlaukkanen/picoclock

MIT License
Copyright (c) 2023 Tommi Laukkanen

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import network
import utime
import http_client
import config

import tm1637
from machine import Pin
from utime import sleep

mydisplay = tm1637.TM1637(clk=Pin(26), dio=Pin(27))
mydisplay.brightness(0)
mydisplay.show("Pico")
sleep(1)

# Disable pylint from wrongly complaining about variable names
# pylint: disable=C0103

# Change to your own city, this is near Tampere, Finland
WEATHER_LATITUDE = "61.3141"
WEATHER_LONGITUDE = "23.7524"
data_time = utime.ticks_ms()
count = 0
current_electricity_price_in_cents = 0
current_weather_text = ""
minutes = 0

def http_get(url):
    """Send HTTP GET request"""
    r = http_client.get(url)
    r.raise_for_status()
    return r.json()

def connect():
    """Connect to WiFi"""
    wlan = network.WLAN(network.STA_IF)
    print("WLAN Active", wlan.active(True))
    sleep(1)
    if not wlan.isconnected():
        print("Connecting to WiFi...")
        wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
        while not wlan.isconnected():
            print("Connecting...")
            sleep(1)
        print("Connected to WiFi")
        sleep(5)


def get_weather():
    """Get weather data from OpenWeatherMap"""
    return http_get("http://api.openweathermap.org/data/2.5/weather?lat=" + WEATHER_LATITUDE +
                    "&lon=" + WEATHER_LONGITUDE +
                    "&appid=" + config.OPENWEATHERMAP_API_KEY + "&units=metric")

def get_time():
    """Get current time from worldtimeapi.org"""
    global data_time
    time_response = http_get('http://worldtimeapi.org/api/timezone/Europe/Helsinki')
    data_time = utime.ticks_ms()
    current_time_seconds = time_response['unixtime']

    # parse utc_offset to seconds
    utc_offset = time_response['utc_offset']
    utc_offset_hours = int(utc_offset[1:3])
    utc_offset_minutes = int(utc_offset[4:6])
    utc_offset_seconds = utc_offset_hours * 3600 + utc_offset_minutes * 60
    current_time_seconds = current_time_seconds + utc_offset_seconds

    return current_time_seconds


def get_current_electricity_price():
    """Get current electricity price from spot-hinta.fi"""
    current_electricity_price = http_get('http://api.spot-hinta.fi/JustNow')
    price_in_cents = int(current_electricity_price['PriceWithTax'] * 1000)
    return price_in_cents

# Show a word
# mydisplay.show("Pico")
# mydisplay.show("    ")
# mydisplay.number(-123)
# mydisplay.numbers(12,59)
# mydisplay.brightness(0)
# mydisplay.scroll("Hello World 123", delay=200)
# mydisplay.temperature(99)


def show_time():
    """Show time on display"""
    global minutes
    time_drift_seconds = int((utime.ticks_ms() - data_time) / 1000)
    current_local_time_with_ticks = current_time + time_drift_seconds
    localtime = utime.localtime(current_local_time_with_ticks)
    hours = localtime[3]
    minutes = localtime[4]
    mydisplay.numbers(hours, minutes)

def show_temp_text(temp_description):
    """Show temperature text on display"""
    mydisplay.show(temp_description)


def show_temp(temp_in_celsius):
    """Show temperature on display"""
    mydisplay.temperature(temp_in_celsius)


def show_spot():
    """Show spot price on display"""
    if current_electricity_price_in_cents < 0:
        mydisplay.show("NEG ")
    else:
        mydisplay.number(current_electricity_price_in_cents)


try:
    mydisplay.show("WIFI")
    connect()
    mydisplay.show("STRT")
    sleep(2)
    print("Getting data")
    mydisplay.show("TIME")
    current_time = get_time()
    show_time()
    sleep(1)
    mydisplay.show("TEMP")
    data = get_weather()
    temperature_with_decimals = data['main']['temp']
    current_weather_text = data['weather'][0]['main']
    temperature = int(temperature_with_decimals)
    show_temp(temperature)
    sleep(1)
    mydisplay.show("SPOT")
    current_electricity_price_in_cents = get_current_electricity_price()
    show_spot()
    sleep(1)

    spot_price_fetched_for_this_hour = False

    while True:
        try:
            count = count + 1
            show_time()
            sleep(10)  # 8
            show_temp_text(current_weather_text)
            sleep(1)  # 2
            show_temp(temperature)
            sleep(2)  # 10
            mydisplay.show("SPOT")
            sleep(1)  # 1
            if current_electricity_price_in_cents < 0:
                mydisplay.show("NEGA")
            elif current_electricity_price_in_cents > 9999:
                mydisplay.show("OVER")
            else:
                mydisplay.number(current_electricity_price_in_cents)
            sleep(2)  # 9

            # Get fresh spot price when minutes = 1
            if minutes == 1 and spot_price_fetched_for_this_hour is False:
                print("Getting spot price")
                current_electricity_price_in_cents = get_current_electricity_price()
                print("Spot price: " + str(current_electricity_price_in_cents))
                spot_price_fetched_for_this_hour = True

            # Reset spot price fetch flag when minutes = 2
            if minutes == 2 and spot_price_fetched_for_this_hour is True:
                spot_price_fetched_for_this_hour = False

            # Get fresh weather data every 30th time = 20s * 30 = 10 minutes
            if count % 30 == 0:
                print("Getting weather data")
                data = get_weather()
                temperature_with_decimals = data['main']['temp']
                temperature = int(temperature_with_decimals)
                current_weather_text = data['weather'][0]['main']
                print("Temperature: " + str(temperature))

            # Fix the clock drift every Xth time
            if count % 3000 == 0:
                current_time = get_time()

            if count == 60000:
                count = 0
        except Exception as e:
            print("Error")
            print(e)
            mydisplay.show("ERR ")

except KeyboardInterrupt:
    print("Exiting")
    mydisplay.show("    ")
    mydisplay.brightness(0)
    wlan = network.WLAN(network.STA_IF)
    wlan.disconnect()
    wlan.active(False)
    print("Disconnected from WiFi")

except Exception as e:
    print("Error")
    print(e)
    mydisplay.show("ERR ")
    mydisplay.brightness(0)
    wlan = network.WLAN(network.STA_IF)
    wlan.disconnect()
    wlan.active(False)
    print("Disconnected from WiFi")
