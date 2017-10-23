from os import listdir, path

if __name__ == "__main__":
    generated_xmls = []
    for file in listdir("config/test_cases"):
        generated_xmls.append(".".join(file.split(".")[0:-1]) + ".xml")
    for file in listdir("config/test_suites"):
        generated_xmls.append(".".join(file.split(".")[0:-1]) + ".xml")

    for file in listdir("generated"):
        if file not in generated_xmls:
            print path.join("generated", file)

