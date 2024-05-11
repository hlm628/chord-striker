FROM --platform=amd64 ubuntu:20.04

WORKDIR /usr/src/app

# install graphviz
RUN apt-get update -y
RUN apt-get install -y graphviz graphviz-dev libgraphviz-dev

# install Python 3.8
RUN apt-get install -y python3.8 python3-pip python3.8-dev python3-pygraphviz

# upgrade pip
RUN python3 -m pip install pip --upgrade


COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# setup pylatex
RUN apt-get update --fix-missing -qq -y \
  && apt-get install -y \
    texlive-latex-base \
    texlive-xetex \ 
    texlive-science \
    texlive-latex-extra \
    texlive-fonts-extra \
    curl \
    wget \  
    git \
    fontconfig \ 
    make \ 
    uuid-runtime \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# install lilypond
RUN wget https://lilypond.org/download/binaries/linux-64/lilypond-2.20.0-1.linux-64.sh
RUN echo | sh lilypond-2.20.0-1.linux-64.sh

CMD [ "/bin/bash" ]
