import csv


def get_student_attendance(student_name):

    total_classes = 30

    present_count = 0

    try:

        with open(
            "attendance.csv",
            "r"
        ) as file:

            reader = csv.reader(file)

            for row in reader:

                if len(row) > 0:

                    if row[0].lower() == student_name.lower():

                        present_count += 1

    except:

        pass

    absent_count = (
        total_classes -
        present_count
    )

    attendance_percentage = (
        present_count /
        total_classes
    ) * 100

    return (
        present_count,
        absent_count,
        round(attendance_percentage, 2)
    )