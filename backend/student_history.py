import csv


def get_attendance_history(student_name):

    records = []

    try:

        with open(
            "attendance.csv",
            "r"
        ) as file:

            reader = csv.reader(file)

            for row in reader:

                if len(row) >= 3:

                    if row[0].lower() == student_name.lower():

                        records.append(
                            {
                                "date": row[1],
                                "time": row[2]
                            }
                        )

    except:
        pass

    return records