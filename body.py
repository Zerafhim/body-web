import datetime
import random


class bmi:
    """Calculate and classify a body's BMI."""

    @staticmethod
    def calculate(weight, height):
        """Return BMI using weight in kilograms and height in meters."""
        if weight < 0:
            raise ValueError("weight must be non-negative")
        if height <= 0:
            raise ValueError("height must be positive")
        return weight / (height ** 2)

    @staticmethod
    def category(value):
        """Return the standard BMI category for a calculated value."""
        if value < 18.5:
            return "Underweight"
        if value < 25:
            return "Normal weight"
        if value < 30:
            return "Overweight"
        return "Obesity"


# Keep the original public names available while exposing the requested class name.
BMI = bmi
Bmi = bmi


exit = False

id = ""
name = ""
gender = ""
age = -1
weight = ""
height = ""
bmi_value = ""

while not exit:
    print("===body information data===")
    print("1. Input new data")
    print("2. View data")
    print("3. Update new data")
    print("4. Delete data")
    print("5. Exit")

    answer = input(" >> ")

    match answer:
        case "1":
            valid_name = False
            while not valid_name:
                input_name = input("Input name [>5 character , contains letter , tittle format:]")
                if len(input_name)>5 and(input_name).replace(" ","").isalpha and (input_name).istitle:
                    valid_name = True
                else:
                    print("Invalid Name , please try again")

            valid_gender = False
            while not valid_gender:
                input_gender = input("Input Gender (M/L) (case sensitive):")
                if input_gender.upper() in ["M" , "L"]:
                    valid_gender = True
                else :
                    print("invalid gender , please try again")

            valid_year = False
            while not valid_year:
                input_year = input("Input birth year [1900-2011]")
                if input_year.isnumeric() and int(input_year) >=1900 and int(input_year) <=2011 :
                    input_year = valid_year
                    valid_year = True
                else:
                    print("invalid birth year , please try again")

            valid_weight = False
            while not valid_weight:
                input_weight = input("Input weight [>=0 kg]")
                if input_weight.isnumeric() and int(input_weight) >= 0:
                    valid_weight = True
                else :
                    print("invalid weight , please try again")

            valid_height = False
            while not valid_height:
                input_height = input("Input height [>=0 cm")
                if input_height.isnumeric() and int(input_height) >= 0:
                    valid_height = True
                else :
                    print("invalid height , please try again") 


            valid_input = valid_name & valid_gender & valid_year & valid_weight & valid_height
            if valid_input:
                age = datetime.datetime.now().year - int(input_year)
                id = "BO" + str(random.randint(100,999))

                name = input_name
                gender = input_gender
                weight = input_weight
                height = input_height
                # BMI calculator here
                bmi_value = bmi.calculate(float(input_weight), float(input_height) / 100)


        case "2":
            print("\nView data")
            if id == "":
                print("\nNo Data")
            else:
                print(f'ID: {id}')
                print(f'name {name}')
                print(f'gender {gender}')
                print(f'age {age}')
                print(f'weight {(weight)}')
                print(f'height {(height)}')
                print(f'bmi {bmi_value}')

                print(f'DY: {id[2:]}')
                print(f'last digit {id[-1:]}')
                print("print success")

        case "3":
            print("\nUpdate new data")
            if id == "":
                print("\nNo Data")
            else:
                print("What do you want to change?")
                print("1. Name")
                print("2. Gender")
                print("3. Birth year")
                print("4. Weight")
                print("5. Height")

                answer = input(" >> ")

                match answer:
                    case "1":
                        valid_name = False
                        while not valid_name:
                            input_name = input("Input name [>5 character , contains letter , tittle format:]")
                            if len(input_name) > 5 and input_name.replace(" ", "").isalpha() and input_name.istitle():
                                valid_name = True
                            else:
                                print("Invalid Name , please try again")

                        print(f"OLd name {name}")
                        print(f"New name {input_name}")
                        name = input_name

                    case "2":
                        valid_gender = False
                        while not valid_gender:
                            input_gender = input("Input Gender (M/L) (case sensitive):")
                            if input_gender.upper() in ["M", "L"]:
                                valid_gender = True
                            else:
                                print("invalid gender , please try again")

                        print(f"OLd gender {gender}")
                        print(f"New gender {input_gender}")
                        gender = input_gender

                    case "3":
                        valid_year = False
                        while not valid_year:
                            input_year = input("Input birth year [1900-2011]")
                            if input_year.isnumeric() and 1900 <= int(input_year) <= 2011:
                                valid_year = True
                            else:
                                print("invalid birth year , please try again")

                        old_age = age
                        new_age = datetime.datetime.now().year - int(input_year)
                        print(f"OLd age {old_age}")
                        print(f"New age {new_age}")
                        age = new_age

                    case "4":
                        valid_weight = False
                        while not valid_weight:
                            input_weight = input("Input weight [>=0 kg]")
                            if input_weight.isnumeric() and int(input_weight) >= 0:
                                valid_weight = True
                            else:
                                print("invalid weight , please try again")

                        print(f"OLd weight {weight}")
                        print(f"New weight {input_weight}")
                        weight = input_weight

                    case "5":
                        valid_height = False
                        while not valid_height:
                            input_height = input("Input height [>=0 cm]")
                            if input_height.isnumeric() and int(input_height) >= 0:
                                valid_height = True
                            else:
                                print("invalid height , please try again")

                        print(f"OLd height {height}")
                        print(f"New height {input_height}")
                        height = input_height

        case "4":
            print("\nDelete data")
            if id == "":
                print("\nNo Data")
            else:
                print(f'ID: {id}')
                print(f'name {name}')
                print(f'gender {gender}')
                print(f'age {age}')
                print(f'weight {(weight)}')
                print(f'height {(height)}')
                print(f'bmi {bmi_value}')

                print(f'DY: {id[2:]}')
                print(f'last digit {id[-1:]}')

                answer = input ("are you sure want to delete this data[y/n]? (case insensitive)").lower()

                if answer == "y":
                    id = ""
                    name = ""
                    gender = ""
                    age = -1
                    weight = ""
                    height = ""
                    bmi_value = "" 
                    print("deleting success ")
                    isdeleting = True    

        case "5":
            print("Exit")
            exit = True

        case _:
            print("Please insert 1-5")