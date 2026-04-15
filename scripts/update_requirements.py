import os
import re
import sys
import requests
import argparse
import subprocess
from tqdm import tqdm
from packaging import version


class RequirementsChecker:
    def __init__(self, requirements_file):
        self.requirements_file = requirements_file
        self.packages = self.get_installed_packages()
        self.latest_packages = []

    def get_installed_packages(self):
        with open(self.requirements_file, 'r') as file:
            packages = file.readlines()
        packages = [pkg.strip() for pkg in packages if pkg.strip()]
        return packages

    def get_latest_version(self, package_name):
        response = requests.get(f"https://pypi.org/pypi/{package_name}/json")
        if response.status_code == 200:
            data = response.json()
            return data['info']['version']
        else:
            print(f"Failed to get data for {package_name}")
            return None

    def parse_package(self, pkg):
        match = re.match(r"([a-zA-Z0-9\-_.]+)([<>=!~]+)([0-9a-zA-Z\-.]+)", pkg)
        if match:
            pkg_name, operator, pkg_version = match.groups()
            return pkg_name, operator, pkg_version
        else:
            return pkg, None, None

    def check_latest_versions(self):
        for pkg in tqdm(self.packages, desc="Checking for updates", bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]"):
            pkg_name, operator, pkg_version = self.parse_package(pkg)
            latest_version = self.get_latest_version(pkg_name)
            if operator and pkg_version:
                if latest_version and version.parse(latest_version) > version.parse(pkg_version):
                    self.latest_packages.append((pkg, f"{pkg_name}=={latest_version}"))
                else:
                    self.latest_packages.append((pkg, pkg))
            else:
                self.latest_packages.append((pkg, pkg))

    def update_requirements_file(self):
        with open(self.requirements_file, 'w') as file:
            for _, latest_pkg in tqdm(self.latest_packages, desc="Updating requirements.txt", bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]", colour="green"):
                file.write(latest_pkg + '\n')

    def install_packages(self):
        for _, latest_pkg in tqdm(self.latest_packages, desc="Installing packages", bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]", colour="green"):
            pkg_name = latest_pkg.split('==')[0]
            subprocess.check_call([sys.executable, "-m", "pip", "install", latest_pkg])

    def run(self):
        self.check_latest_versions()

        print("The following packages have newer versions available:")
        updates_available = False
        for current, latest in self.latest_packages:
            if current != latest:
                print(f"{current} -> {latest}")
                updates_available = True

        if updates_available:
            confirm = input("Do you want to update the requirements.txt file with these latest versions? (yes/y to confirm): ")
            if confirm.lower() in ['yes', 'y']:
                self.update_requirements_file()
                print("requirements.txt has been updated.")
                if 'VIRTUAL_ENV' in os.environ:
                    self.install_packages()
                    print("Packages have been installed.")
                else:
                    print("Virtual environment not detected. Skipping package installation.")
            else:
                print("requirements.txt has not been updated.")
        else:
            print("All packages are up-to-date.")


def main():
    parser = argparse.ArgumentParser(description="Check for latest versions of packages in requirements.txt.")
    parser.add_argument('requirements_file', type=str, help="Path to the requirements.txt file")
    args = parser.parse_args()

    checker = RequirementsChecker(args.requirements_file)
    checker.run()


if __name__ == "__main__":
    main()
