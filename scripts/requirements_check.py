import requests
import re
from packaging import version


def get_installed_packages(requirements_file):
    with open(requirements_file, 'r') as file:
        packages = file.readlines()
    packages = [pkg.strip() for pkg in packages if pkg.strip()]
    return packages


def get_latest_version(package_name):
    response = requests.get(f"https://pypi.org/pypi/{package_name}/json")
    if response.status_code == 200:
        data = response.json()
        return data['info']['version']
    else:
        print(f"Failed to get data for {package_name}")
        return None


def parse_package(pkg):
    match = re.match(r"([a-zA-Z0-9\-_.]+)([<>=!~]+)([0-9a-zA-Z\-.]+)", pkg)
    if match:
        pkg_name, operator, pkg_version = match.groups()
        return pkg_name, operator, pkg_version
    else:
        return pkg, None, None


def check_latest_versions(requirements_file, output_file):
    packages = get_installed_packages(requirements_file)
    latest_packages = []

    for pkg in packages:
        pkg_name, operator, pkg_version = parse_package(pkg)
        latest_version = get_latest_version(pkg_name)
        if operator and pkg_version:
            if latest_version and version.parse(latest_version) > version.parse(pkg_version):
                latest_packages.append(f"{pkg_name}=={latest_version}")
            else:
                latest_packages.append(pkg)
        else:
            latest_packages.append(pkg)

    with open(output_file, 'w') as file:
        for pkg in latest_packages:
            file.write(pkg + '\n')

    print(f"Updated requirements have been written to {output_file}")


if __name__ == "__main__":
    requirements_file = '../requirements.txt'
    output_file = 'update_requirements.txt'
    check_latest_versions(requirements_file, output_file)
