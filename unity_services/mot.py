from datetime import datetime as dt

import discord
import httpx
from colour import Color as Colour

from unity_util import bot_config


class OdometerReading:
    def __init__(self, value: str, unit: str):
        self.value: int = int(value)
        self.unit: str = unit


class Comment:
    def __init__(self, data: dict):
        self.text: str = data["text"]
        self.type: str = data["type"]


class MotTest:
    def __init__(self, test):
        self.result: str = test["testResult"]
        self.completed_date = dt.strptime(test["completedDate"], "%Y.%m.%d %H:%M:%S")
        if self.result != "FAILED":
            self.expiry_date = dt.strptime(test["expiryDate"], "%Y.%m.%d")
        self.odometer_reading: OdometerReading = OdometerReading(test["odometerValue"], test["odometerUnit"])
        self.comments: tuple[Comment] = tuple([Comment(i) for i in test["rfrAndComments"]])
        self.id = int(test["motTestNumber"])


class Vehicle:
    def __init__(self, data: dict):
        self.registration = data["registration"]
        if "manufactureYear" in data:
            self.registration_date = dt.strptime(data["manufactureYear"], "%Y")
        else:
            self.registration_date = dt.strptime(data["firstUsedDate"], "%Y.%m.%d")
        self.make = data["make"].capitalize()
        self.model = data["model"].capitalize()
        self.fuel_type = data["fuelType"]
        self.colour = data["primaryColour"]
        self.tests = tuple([MotTest(i) for i in data["motTests"]]) if "motTests" in data else tuple([])
        if self.tests:
            self.embeds = tuple([self.make_embed(i) for i in range(len(self.tests))])
        else:
            self.mot_expiry_date = dt.strptime(data["motTestExpiryDate"], "%Y-%m-%d")
            self.embeds = tuple([self.make_basic_embed()])

    def make_basic_embed(self):
        c = Colour(self.colour).rgb
        new_c = discord.Colour.from_rgb(int(c[0] * 255), int(c[1] * 255), int(c[2] * 255))
        embed = discord.Embed(
            title=f"{self.registration_date.year} {self.make} {self.model}",
            colour=new_c,
        )
        embed.add_field(
            name="MOT Expiry",
            value=self.mot_expiry_date.strftime("%d/%m/%Y"),
            inline=True,
        )
        embed.add_field(name="Colour", value=self.colour, inline=True)
        return embed

    def make_embed(self, test_index) -> discord.Embed:
        c = Colour(self.colour).rgb
        new_c = discord.Colour.from_rgb(int(c[0] * 255), int(c[1] * 255), int(c[2] * 255))
        test = self.tests[test_index]
        embed = discord.Embed(
            title=f"{self.registration_date.year} {self.make} {self.model}",
            colour=new_c,
        )
        embed.add_field(name="MOT Result", value=test.result, inline=True)
        embed.add_field(name="MOT Date", value=test.completed_date.strftime("%d/%m/%Y"), inline=True)
        if test.result == "FAILED":
            embed.add_field(name="MOT Expiry", value="N/A", inline=True)
        else:
            embed.add_field(
                name="MOT Expiry",
                value=test.expiry_date.strftime("%d/%m/%Y"),
                inline=True,
            )
        embed.add_field(
            name="MOT Mileage",
            value="{val:,}{}".format(test.odometer_reading.value, test.odometer_reading.unit),
            inline=True,
        )
        embed.add_field(name="MOT Number", value=test.id, inline=True)
        embed.add_field(name="Car Colour", value=self.colour, inline=True)
        return embed


async def get_vehicle(registration: str) -> Vehicle:
    headers = {"x-api-key": bot_config.DVLA_API_KEY}
    url = f"https://beta.check-mot.service.gov.uk/trade/vehicles/mot-tests/?registration={registration}"
    async with httpx.AsyncClient() as client:
        data = await client.get(url, headers=headers)
        json = data.json()

    if "httpStatus" in json:  # 404
        return None

    return Vehicle(json[0])
