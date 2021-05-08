import threading
import sys
import time
import logging
import Adafruit_DHT as dht
import board
import busio
import adafruit_tsl2591
import mariadb
import datetime
import RPi.GPIO as GPIO
import MCP3008 as MCP
import SPI
import smtplib
import ssl
import mode
import Maestro
import math
import statistics
from gpiozero import Button
from email.mime.text import MIMEText
from adafruit_seesaw.seesaw import Seesaw
"""
basic concept for the entire project
Have a main menu function that creates a bunch of threads (4 max)
Within each thread, there is a while true loop, keeps grabbing data, sleeps for 2 minutes when its
done with its specific tasks, then repeats
"""


class data:
    """
    This class is used to transport data to and from different threads that might need this information. 
    Currently, there is no stopping race conditions.  
    """
    def __init__(self,temp,humid,heat,cool,light,vent,shade,water,action):
        self.temp = temp
        self.humid = humid
        self.heat = heat
        self.cool = cool
        self.light = light
        self.vent = vent
        self.shade = shade
        self.water = water
        self.action = action

def noData(sensName):
    """ 
    This function is used to send an email if there was an issue trying to access the database and either it failed to open and get data from a table. 
    There are two instances of this function, this one, and one that will directly follow it. 
    The reason for this difference is that the sensors that access this function are integral to the systems functionality (Soil Mositure, Internal Temperature, etc)
    """
    SMTP_SERVER = 'smtp.gmail.com' #Email Server 
    SMTP_PORT = 587 #Server Port 
    GMAIL_USERNAME = 'Automated.Greenhouse.ttu@gmail.com' 
    GMAIL_PASSWORD = ''
    msg = MIMEText("""Hello, I am the Automated Greenhouse. There was an issue gathering data for the {}. Could you send out an engineer to fix me? Thank you
    This sensor is integral to the greenhouse's automation, so I will be shutting down until I am fixed.
    **This is an automated message, responding to this will not notify anyone.**""".format(sensName))
    me = 'Automated.Greenhouse.TTU@gmail.com'
    you = 'tpwmustang@gmail.com'
    msg['Subject'] = 'ERROR: Greenhouse Issues!'
    msg['From'] = me
    msg['To'] = you
    s = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    s.starttls()
    s.login(GMAIL_USERNAME, GMAIL_PASSWORD)
    s.send_message(msg)
    s.quit() 
    sys.exit(1)

def noDataExt(sensName):
    """ 
    This function is used to send an email if there was an issue trying to access the database and either it failed to open and get data from a table. 
    This function is only accessed by sensors that are NOT integral to the system (Exterior Temperature/Humidity, Wind Speed, Rain, Etc.)
    """
    SMTP_SERVER = 'smtp.gmail.com' #Email Server 
    SMTP_PORT = 587 #Server Port 
    GMAIL_USERNAME = 'Automated.Greenhouse.ttu@gmail.com' 
    GMAIL_PASSWORD = '' 
    msg = MIMEText("""Hello, I am the Automated Greenhouse. There was an issue gathering data for the {}. Could you send out an engineer to fix me? Thank you
    This sensor is NOT integral to the greenhouse's automation, so I will NOT be shutting down. 
    **This is an automated message, responding to this will not notify anyone.**""".format(sensName))
    me = 'Automated.Greenhouse.TTU@gmail.com'
    you = 'tpwmustang@gmail.com'
    msg['Subject'] = 'ERROR: Greenhouse Issues!'
    msg['From'] = me
    msg['To'] = you
    s = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    s.starttls()
    s.login(GMAIL_USERNAME, GMAIL_PASSWORD)
    s.send_message(msg)
    s.quit() 

def dataStorageFail(sensName):
    SMTP_SERVER = 'smtp.gmail.com' #Email Server 
    SMTP_PORT = 587 #Server Port 
    GMAIL_USERNAME = 'Automated.Greenhouse.ttu@gmail.com' 
    GMAIL_PASSWORD = '' 
    msg = MIMEText("""Hello, I am the Automated Greenhouse. There was an issue storing data for the {}. Could you please send out an engineer to fix me? Thank you
    This is an integral part of the greenhouse's automation, so I will be shutting down.
    **This is an automated message, responding to this will not notify anyone.**""".format(sensName))
    me = 'Automated.Greenhouse.TTU@gmail.com'
    you = 'tpwmustang@gmail.com'
    msg['Subject'] = 'ERROR: Greenhouse Issues!'
    msg['From'] = me
    msg['To'] = you
    s = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    s.starttls()
    s.login(GMAIL_USERNAME, GMAIL_PASSWORD)
    s.send_message(msg)
    s.quit() 
    sys.exit(1)

def average(inp):
    """
    Simple average algorithm. 
    Takes in array input, finds the total length and the total of all points added together, returns the average. 
    """
    count = 0
    total = 0
    for x in inp:
        count += 1
        total += x
    return (total/count)

def total(inp):
    """
    Simple Total algorithm. 
    Takes in array input, finds the total of all the points added together, and returns it
    """
    total = 0
    for x in inp:
        total += x
    return total

def dailyEmail():
    """
    This function sends out the daily email. 
    """
    SMTP_SERVER = 'smtp.gmail.com' #Email Server 
    SMTP_PORT = 587 #Server Port 
    GMAIL_USERNAME = 'Automated.Greenhouse.ttu@gmail.com' 
    GMAIL_PASSWORD = ''
    lister = []
    inp = []
    Max = 0
    Min = 0
    try:
        cur.execute("""SELECT * FROM temperature WHERE taken_at > "{}" AND taken_at < "{}";""".format((datetime.datetime.now()-datetime.timedelta(days=9)).strftime("%Y-%m-%d"),datetime.datetime.now().strftime("%Y-%m-%d")))#Internal Temp
        for id, temp, taken_at in cur:
            lister.append(temp)
            if Max <= temp:
                Max = temp
            if Min >= temp and temp != 0:
                Min = temp
        inp.append(average(lister))#average temp, 0
        inp.append(Max)#max temp, 1
        inp.append(Min)#min temp, 2
        Max = 0
        Min = 0
        lister.clear()
        cur.execute("""SELECT * FROM humidity WHERE taken_at > "{}" AND taken_at < "{}";""".format((datetime.datetime.now()-datetime.timedelta(days=9)).strftime("%Y-%m-%d"),datetime.datetime.now().strftime("%Y-%m-%d")))#Internal Humid
        for id, humid, taken_at in cur:
            lister.append(humid)
            if Max <= humid:#max humidity
                Max = humid
            if Min >= humid and humid != 0:#min humidity
                Min = humid
        inp.append(average(lister))#average Humid, 3
        inp.append(Max)#max humid, 4
        inp.append(Min)#min Humid, 5
        Max = 0
        Min = 0
        lister.clear()
        cur.execute("""SELECT * FROM temp_ext WHERE taken_at > "{}" AND taken_at < "{}";""".format((datetime.datetime.now()-datetime.timedelta(days=9)).strftime("%Y-%m-%d"),datetime.datetime.now().strftime("%Y-%m-%d")))#External Temp
        for id, temp, taken_at in cur:
            lister.append(temp)
            if Max <= temp:
                Max = temp
            if Min >= temp and temp != 0:
                Min = temp
        inp.append(average(lister))
        inp.append(Max)
        inp.append(Min)
        Max = 0
        Min = 0
        lister.clear()
        cur.execute("""SELECT * FROM humid_ext WHERE taken_at > "{}" AND taken_at < "{}";""".format((datetime.datetime.now()-datetime.timedelta(days=9)).strftime("%Y-%m-%d"),datetime.datetime.now().strftime("%Y-%m-%d")))#External Humid
        for id, humid, taken_at in cur:
            lister.append(humid)
            if Max <= humid:
                Max = humid
            if Min >= humid and humid != 0:
                Min = humid
        inp.append(average(lister))
        inp.append(Max)
        inp.append(Min)
        Max = 0
        Min = 0
        lister.clear()
        cur.execute("""SELECT * FROM wind_direction WHERE taken_at > "{}" AND taken_at < "{}";""".format((datetime.datetime.now()-datetime.timedelta(days=9)).strftime("%Y-%m-%d"),datetime.datetime.now().strftime("%Y-%m-%d")))#Wind Direction
        for id,letterDire,numberDire,taken_at in cur:
            lister.append(letterDire)
        inp.append(mode.mode(lister))
        lister.clear()
        cur.execute("""SELECT * FROM wind_speed WHERE taken_at > "{}" AND taken_at < "{}";""".format((datetime.datetime.now()-datetime.timedelta(days=9)).strftime("%Y-%m-%d"),datetime.datetime.now().strftime("%Y-%m-%d")))#Wind Speed
        for id, speed, taken_at in cur:
            lister.append(speed)
            if Max <= speed:
                Max = speed
        inp.append(average(lister))
        inp.append(Max)
        Max = 0
        Min = 0
        lister.clear()
        cur.execute("""SELECT * FROM ppfd WHERE taken_at > "{}" AND taken_at < "{}";""".format((datetime.datetime.now()-datetime.timedelta(days=9)).strftime("%Y-%m-%d"),datetime.datetime.now().strftime("%Y-%m-%d")))#PPFD
        for id, ppfd, taken_at in cur:
            lister.append(ppfd)
        inp.append(average(lister))
        Max = 0
        Min = 0
        lister.clear()
        cur.execute("""SELECT * FROM rainfall WHERE taken_at > "{}" AND taken_at < "{}";""".format((datetime.datetime.now()-datetime.timedelta(days=9)).strftime("%Y-%m-%d"),datetime.datetime.now().strftime("%Y-%m-%d")))#Rain
        for id, rain, taken_at in cur:
            if Max <= rain:
                Max = rain
        inp.append(Max)
        Max = 0
        Min = 0
        lister.clear()
        cur.execute("""SELECT * FROM soil_moisture WHERE taken_at > "{}" AND taken_at < "{}";""".format((datetime.datetime.now()-datetime.timedelta(days=9)).strftime("%Y-%m-%d"),datetime.datetime.now().strftime("%Y-%m-%d")))#Soil Moisture
        for id, moisture, taken_at in cur:
            lister.append(moisture)
        inp.append(average(lister))
        Max = 0
        Min = 0
        mess = """\tHello, I am the Automated Greenhouse!
        Here is todays daily report:
        Greenhouse Internal Temperature: Avg: {} F High: {} F Low: {} F
        Greenhouse Internal Humidity:    Avg: {}% High: {}% Low: {}%
        Greenhouse External Temperature: Avg: {} F High: {} F Low: {} F
        Greenhouse External Humidity:    Avg: {}% High: {}% Low: {}%
        External Wind Direction:         Avg: {}
        External Wind Speed:             Avg: {} MPH High: {} MPH
        Internal Light Intensity:        Avg: {} μmol/s/m2
        Rainfall:                        Total: {} Inches
        Soil Moisture:                   Avg: {} %
        """.format(inp[0],inp[1],inp[2],inp[3],inp[4],inp[5],inp[6],inp[7],inp[8],inp[9],inp[10],inp[11],inp[12],inp[13],inp[14],inp[15],inp[16],inp[17])
        actions ="""
        Here are the actions taken in the greenhouse today:
        Number of times drip irrigation was activated: {} Times
        Number of times shade system was activated: {} Times
        Number of times heating system was activated: {} Times
        Number of times cooling system was activated: {} Times
        Number of times venting system was activated: {} Times
        Number of times lighting system was activated: {} Times
         """.format(dataPasser.action[0], dataPasser.action[1],dataPasser.action[2],dataPasser.action[3],dataPasser.action[4],dataPasser.action[5])
        msg = MIMEText(mess+actions)
        me = 'Automated.Greenhouse.ttu@gmail.com'
        you = 'tpwmustang@gmail.com, hunter.hughes@ttu.edu'
        msg['Subject'] = "Daily Generated Report: {}".format(datetime.date.today())
        msg['From'] = me
        msg['To'] = you
        s = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        s.starttls()
        s.login(GMAIL_USERNAME, GMAIL_PASSWORD)
        s.send_message(msg)
        s.quit()
    except mariadb.Error as e:
        print(f"Error: {e}")
        cleanExit()

def cleanExit():
    """
    Clean Exit function.
    This function makes sure that every sensor that controls an exterior system. Such as the Light System. 
    Only called when an exception is thrown and system requires shutdown. 
    """
    if dataPasser.light == 1:
        #turn lights off
        GPIO.output(23,False)
    if dataPasser.shade == 1:
        #turn off shade
        servo2.ChangeDutyCycle(10)
        time.sleep(5)
        servo2.ChangeDutyCycle(0)
    if dataPasser.vent == 1:
        #Close Vents
        servo2.ChangeDutyCycle(10)
        time.sleep(.6)              
        servo2.ChangeDutyCycle(0)
    if dataPasser.water == 1:
        #Turn off drip irrigation
        GPIO.output(12,False)
    sys.exit(1)

def Interior(name): #Thread 1
    #This should include DHT22, Lux, Shade System, and Light System. 
    shade = 0 #Either 0 or 1, shade off or on
    lights = 0 #Either 0 or 1, lights off or on
    countDHT = 0 #Counter, counts up if sensor did not collect data
    countTSL = 0 #Counter, counts up if sensor did not collect data
    vent = 0 #Vent state, Either 0 or 1, Vent closed or open
    servo = GPIO.PWM(13,50)
    servo.start(0)
    servo2 = GPIO.PWM(19,50)
    servo2.start(0)
    while True:
        time.sleep(5)
        humid, temp = dht.read_retry(dht.DHT22,4)
        print(temp)
        print(humid)
        if humid is not None and temp is not None:
            countDHT = 0
            try:
                logging.info("Thread %s: Logging Interior Temp/Humid into MariaDB",name)
                tempin = temp*(9/5)+32
                cur.execute("INSERT INTO temperature (temp,taken_at) VALUES (?,?)", (tempin,datetime.datetime.now()))
                cur.execute("INSERT INTO humidity (humid,taken_at) VALUES (?,?)", (humid,datetime.datetime.now()))
                conn.commit()
            except mariadb.Error as e:
                print(f"Error: {e}")
                dataStorageFail("DHT22")
                cleanExit()
            dataPasser.temp = tempin
            dataPasser.humid = humid
            
        else:
            print("Interior DHT Data could not be retrieved")
            countDHT = countDHT + 1 #Counts here bc data was not collect
        #Vent System here
        if humid is not None and temp is not None:
            if humid >= 80:
                #Open Vent here
                servo2.ChangeDutyCycle(4)
                time.sleep(.8)
                servo2.ChangeDutyCycle(0)
                vent = 1
            else:
                if(vent == 1):
                    #Close Vent here
                    servo2.ChangeDutyCycle(10)
                    time.sleep(.6)              
                    servo2.ChangeDutyCycle(0)
                    vent = 0
        #This begins the light portion
        #PPFD = Lux * .0232
        lux = light.lux
        
        if lux is not None:
            PPFD = (4*.232*lux)
            print(PPFD)
            if PPFD >= 800:
                if shade != 1 and lights != 1:
                    #Shade on
                    logging.info("Thread {}: Turning shade on.".format(name))
                    servo.ChangeDutyCycle(4)
                    time.sleep(4.55)              
                    servo.ChangeDutyCycle(0)
                    shade = 1
                    dataPasser.action[1] += 1
                elif lights == 1 and shade != 1:
                    #turn lights off
                    logging.info("Thread {}: Turning lights off.".format(name))
                    GPIO.output(23, False)
                    lights = 0
                elif shade == 1 and lights == 1:
                    #turn lights off
                    logging.info("Thread {}: turning lights off.".format(name))
                    GPIO.output(23,False)
                    lights = 0
                else:
                    logging.info("Thread {}: No change for Lights/Shade".format(name))
                    pass
            elif PPFD <= 200:
                #Lights
                if shade == 1 and lights != 1:
                    #shade off
                    logging.info("Thread {}: Turning off shade.".format(name))
                    servo.ChangeDutyCycle(10)
                    time.sleep(5)
                    servo.ChangeDutyCycle(0)
                    shade = 0
                elif shade != 1 and lights != 1:
                    #lights on
                    logging.info("Thread {}: Turning on lights.".format(name))
                    GPIO.output(23,True)
                    lights = 1
                    dataPasser.action[5] += 1
                elif shade == 1 and lights == 1:
                    #shade off
                    logging.info("Thread {}: Turning off shade.".format(name))
                    servo.ChangeDutyCycle(10)
                    time.sleep(5)
                    servo.ChangeDutyCycle(0)
                    shade = 0
                else:
                    logging.info("Thread {}: no change for lights/shade".format(name))
                    pass
            else:
                logging.info("Thread {}: no change for lights/shade".format(name))
                pass #Do nothing here as no change is needed
            #Store PPFD HERE
            try:
                logging.info("Thread %s: Logging PPFD into MariaDB",name)
                cur.execute("INSERT INTO ppfd (ppfd,taken_at) VALUES (?,?)", (PPFD,datetime.datetime.now()))
                conn.commit()
            except mariadb.Error as e:
                print(f"Error: {e}")
                dataStorageFail("TSL2591")
                cleanExit()
        else:
            print("TSL2591 Data could not be retrieved")
            countTSL = countTSL + 1
        time.sleep(55)
        
        if countDHT >= 5:
            noData("DHT22")
            #Dont need anything after this, as it will close Pi
        if countTSL >= 5:
            noData("TSL2591")
            #Dont need anything after this, as it will close Pi
        

def temperatureControl(name): #Thread 2
    #NO DATA STORAGE IN THIS THREAD
    #Currently sleeps for one minute before rechecking values. (Meaningless since values get updated every 2 mins)
    GPIO.output(22,False)
    GPIO.output(27,False)
    GPIO.output(17,False)
    sent = 0
    while True:
        cool = 0
        heat = 0
        time.sleep(15)
        temp = dataPasser.temp
        
        if temp >= 80 and cool != 1:
            #activate cooling
            logging.info("Thread %s: Activating cooling system",name)
            GPIO.output(27,True)
            time.sleep(5)
            GPIO.output(27,False)
            GPIO.output(22,True)
            cool = 1
            dataPasser.action[3] += 1
        elif temp <= 80 and cool == 1:
            #turn cooling off
            logging.info("Thread %s: Deactivating cooling system",name)
            GPIO.output(27,False)
            GPIO.output(22,False)
            cool = 0
        elif temp <= 40 and heat != 1:
            #activate heating
            logging.info("Thread %s: Activating heating system",name)
            GPIO.output(17,True)
            GPIO.output(27,False)
            heat = 1
            dataPasser.action[2] = dataPasser.action[2] + 1
        elif temp >=40 and heat == 1:
            #turn heating off
            logging.info("Thread %s: Deactivating heating system",name)
            GPIO.output(17,False)
            GPIO.output(27,False)
            heat = 0
        else:
            #temp was fine and no system was already active, or system is active and still needs to be...
            pass
        temp = 0
        if datetime.datetime.now().strftime("%H:%M:%S") >= "20:00:00" and sent != 1:
            logging.info("Thread %s: Sending automated email",name)
            #dailyEmail()
            sent = 1
        if datetime.datetime.now().strftime("%H:%M:%S") >= "00:00:00" and datetime.datetime.now().strftime("%H:%M:%S") <= "01:00:00" and sent == 1:
            sent = 0
        time.sleep(30)
def Exterior(name): #Thread 3
    countDHTout = 0
    countWind = 0
    wind_count = 0
    radius_cm = 9
    interval = 5
    store_speeds = []
    wind_gust = 0
    water_const = 0.2794 #Millimiters of water :)
    rain_count = 0
    store_rain = []
    mmToIn = .0393
    total_rain = 0
    def spin():
        global wind_count
        wind_count = wind_count + 1
    def rain():
        global rain_count
        rain_count += 1
    def reset_rain():
        global rain_count
        rain_count = 0
    def rainfall(time_sec):
        global rain_count  
        water = rain_count * water_const * mmToIn
        return (water/time_sec)
    
    wind_speed_sensor = Button(16)
    wind_speed_sensor.when_pressed = spin
    SPI_PORT   = 0
    SPI_DEVICE = 0
    mcp = MCP.MCP3008(spi=SPI.SpiDev(SPI_PORT, SPI_DEVICE))
    store_dire =[]
    rain_gauge_sensor = Button(26)
    rain_gauge_sensor.when_pressed = rain
    
    
    def reset_wind():
        global wind_count
        wind_count = 0

    def calculate_speed(time_sec):
        global wind_count
        circumference_cm = (2 * math.pi) * radius_cm
        rotations = wind_count / 2
    
        dist_cm = circumference_cm * rotations
        dist_miles = dist_cm / 160934.4
    
        time_hr = time_sec / 3600
    
        speed = dist_miles / time_hr
    
        return speed

    def convert(input):
        """Converts the value from the MCP value to the actual wind direction\n
        Returns a Tuple data type"""
        switch = {
            752: ("N",0),
            92: ("E",90),
            285: ("S",180),
            890: ("W",270),
            455: ("NE",45),
            183: ("SE",135),
            611: ("SW",225),
            840: ("NW",315),
            400: ("NNE",22.5),
            83: ("ENE",67.5),
            65: ("ESE",112.5),
            126: ("SSE",157.5),
            243: ("SSW",202.5),
            583: ("WSW",247.5),
            790: ("WNW",292.5),
            660: ("NNW",337.5)
                }
        return switch.get(input,-1)

    #WORK NEEDED HERE FOR TABLE STUFF
    while True:
        humid, temp = dht.read_retry(dht.DHT22, 24)
        if humid is not None and temp is not None:
            countDHTout = 0
            try:
                logging.info("Thread %s: Logging External Temp/Humid into MariaDB",name)
                tempin = temp*(9/5)+32
                cur.execute("INSERT INTO temp_ext (temp,taken_at) VALUES (?,?)", (tempin,datetime.datetime.now()))
                cur.execute("INSERT INTO humid_ext (humid,taken_at) VALUES (?,?)", (humid,datetime.datetime.now()))
                conn.commit()
            except mariadb.Error as e:
                print(f"Error: {e}")
                dataStorageFail("External DHT22")
                cleanExit()
        else:
            print("External DHT Data could not be retrieved")
            countDHTout = countDHTout + 1 #Counts here bc data was not collected
        
        #shoving more stuff in here than usual, PLZ TEST ME :)
        start_time = time.time()
        while time.time() - start_time <= interval:
            reset_wind()
            time.sleep(interval)
            final_speed = calculate_speed(interval)
            store_speeds.append(final_speed)
            if (wind_gust <= max(store_speeds)):
                wind_gust = max(store_speeds)
            windSpeed = statistics.mean(store_speeds)
            store_speeds.clear()

            reset_rain()
            time.sleep(interval)
            final_rain = rainfall(interval)
            store_rain.append(final_rain)
            for x in store_rain:
                total_rain += x
            print("rain value:",final_rain,"inches over 5 seconds")
            print("total rain of day:",total_rain,"inches")
            store_rain.clear()
            wind = mcp.read_adc(0)
            store_dire.append(wind)
            most = mode.mode(store_dire)
            windDirection = convert(most)
            if windDirection == -1:
                most = most -6
            while windDirection == -1:
                most += 1
                windDirection = convert(most)
        if windSpeed is not None and windDirection is not None:
            try:
                logging.info("Thread %s: Logging wind Dire/Speed into MariaDB",name)
                cur.execute("INSERT INTO wind_direction (letterDire,numberDire,taken_at) VALUES (?,?,?)", (windDirection[0],windDirection[1],datetime.datetime.now()))
                cur.execute("INSERT INTO wind_speed (speed,taken_at) VALUES (?,?)", (windSpeed,datetime.datetime.now()))
                cur.execute("INSERT INTO rainfall (rain,taken_at) VALUES (?,?)", (total_rain,datetime.datetime.now()))
                conn.commit()
            except mariadb.Error as e:
                print(f"Error: {e}")
                dataStorageFail("Anemometer/Wind Vane")
        
        else:
            print("External Wind Data was not collected")
            countWind = countWind + 1
            #counts here bc data was not collected. 
        
        if countDHTout >= 5:
            #Send email, but no shut off
            noDataExt("DHT22")
            countDHTout = 0
        if countWind >= 5:
            #Send email, but no shut off
            noDataExt("Wind System")
            countWind = 0
        
def soil(name): #Thread 4
    i2c_bus = busio.I2C(board.SCL, board.SDA)
    ss = Seesaw(i2c_bus, addr=0x36)
    countStemma = 0
    while True:
        # read moisture level through capacitive touch pad
        touch = ss.moisture_read()
        if touch is not None:
            satPercent = 200*(touch-200)/1800
            try:
                logging.info("Thread %s: Logging soil info into MariaDB",name)
                cur.execute("INSERT INTO soil_moisture (moisture,taken_at) VALUES (?,?)", (satPercent,datetime.datetime.now()))
                conn.commit()
            except mariadb.Error as e:
                print(f"Error: {e}")
                dataStorageFail("Soil Moisture Sensor")
        else:
            print("Stemma Data could not be collected")
            countStemma += 1
            #Didn't collect value
        if satPercent >= 60:
            #drip off
            GPIO.output(12,False)
        elif satPercent <= 40:
            #drip on
            GPIO.output(12,True)
            dataPasser.action[0] += 1
        else:
            continue
            #no change drip
        if countStemma >= 5:
            noData("Stemma Soil Moisture Sensor")
        time.sleep(30)

if __name__ == "__main__":
    conn = mariadb.connect(
        user="root",
        password="123",
        host="localhost",
        database="greenhouse"
        )
    cur = conn.cursor()
    I2C = busio.I2C(board.SCL,board.SDA)
    light = adafruit_tsl2591.TSL2591(I2C)
    servo = Maestro.Controller()
    dataPasser = data(70,0,0,0,0,0,0,0,[0,0,0,0,0,0])
    format="%(asctime)s: %(message)s"
    logging.basicConfig(format=format, level=logging.INFO, datefmt="%H:%M:%S")
    w = threading.Thread(target=Interior,args=(1,))
    x = threading.Thread(target=temperatureControl,args=(2,))
    y = threading.Thread(target=Exterior,args=(3,))
    z = threading.Thread(target=soil,args=(4,))
    GPIO.setup(12,GPIO.OUT)#irrigation system
    GPIO.setup(23,GPIO.OUT)#lighting system
    GPIO.setup(17,GPIO.OUT)#heating system
    GPIO.setup(27,GPIO.OUT)#cooling SOLENOID
    GPIO.setup(22,GPIO.OUT)#cooling FAN
    GPIO.setup(19,GPIO.OUT)#Vent servo
    GPIO.setup(13,GPIO.OUT)#Shade servo
    time.sleep(1)
    GPIO.output(17,False)
    GPIO.output(12,False)
    GPIO.output(23,False)
    GPIO.output(22,False)
    GPIO.output(27,False)
    time.sleep(1)
    w.start()
    x.start()
    y.start()
    z.start()
    logging.info("Main: Threads Started…")
    w.join()
    x.join()
    y.join()
    z.join()

   


 



