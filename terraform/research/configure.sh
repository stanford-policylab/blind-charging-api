#!/bin/bash

##############################################################################
# ENVIRONMENT VARIABLES
#
# Set versions for the software to be installed.
# ----------------------------------------------------------------------------
# R versions correspond to Rocker releases, but don't prefix the R:
# https://github.com/rocker-org/rocker-versioned2/releases
R_VERSION="4.4.1"
R_HOME="/usr/local/lib/R"
TZ="Etc/UTC"
LANG=en_US.UTF-8
CRAN=https://p3m.dev/cran/__linux__/noble/latest
S6_VERSION="v2.1.0.2"
RSTUDIO_VERSION="2024.04.2+764"
DEFAULT_USER="rstudio"
# Python versions: https://www.python.org/downloads/source/
PYTHON_VERSION="3.12.7"
##############################################################################

# Update system packages
sudo apt-get update -y
sudo apt-get upgrade -y

# Install git with SSL
sudo apt-get install -y \
    --no-install-recommends \
    git-all

# Clone the rocker project and delegate to their shell scripts to finish setup.
git clone https://github.com/rocker-org/rocker-versioned2.git
cd rocker-versioned2
# Check out a known version for predictability.
git checkout "R$ROCKER_VERSION"
# Alias the ./scripts directory as /rocker-scripts, since this is how they
# would appear in the Docker image.
sudo ln -s "$(pwd)/scripts" /rocker-scripts

# Install R
sudo /rocker_scripts/setup_R.sh
# Install Tidyverse
sudo /rocker_scripts/install_tidyverse.sh
# Install RStudio
sudo /rocker_scripts/install_rstudio.sh
sudo /rocker_scripts/install_s6init.sh
sudo /rocker_scripts/default_user.sh
sudo /rocker_scripts/init_set_env.sh
sudo /rocker_scripts/init_userconf.sh
sudo /rocker_scripts/pam-helper.sh
sudo /rocker_scripts/install_rstudio.sh
sudo /rocker_scripts/install_pandoc.sh
sudo /rocker_scripts/install_quarto.sh

# Install R packages
install2.r --error --skipmissing --skipinstalled -n "$NCPUS" \
    askpass \
    base64enc \
    dplyr \
    glue \
    grid \
    janitor \
    jsonlite \
    parallel \
    png \
    purrr \
    qpdf \
    readxl \
    reticulate \
    rstudioapi \
    stringr \
    tibble \
    tidyr \
    tidyverse \
    writexl \
    yaml
# Install `diffmatchpatch` from Alex's fork which fixes a buffer overflow error.
installGithub.r chohlasa/diffmatchpatch@348b333

# Install Python
sudo /rocker_scripts/install_python.sh
sudo /rocker_scripts/install_pyenv.sh
# Install and set the python version to the one specified in the env using pyenv
pyenv install $PYTHON_VERSION
pyenv global $PYTHON_VERSION
# Install Jupyter
sudo /rocker_scripts/install_jupyter.sh

# Clean up
sudo apt-get clean
rm -rf /tmp/downloaded_packages/
rm -rf /rocker_scripts
cd ..
rm -rf rocker-versioned2

echo "Setup complete!"
