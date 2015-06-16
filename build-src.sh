#!/bin/sh

VERSION=`grep "VERSION =" fakeregks.py | sed s'/^.*"\([[:digit:]\.]\+\)"/\1/'`
NAME="faketure"

# Update
git pull --rebase

# Cleanup
rm -f $NAME-*.tar.bz2
find . | grep '.pyc$' | xargs rm 2>/dev/null
find . | grep '~$' | xargs rm 2>/dev/null

# Archive
mkdir $NAME-$VERSION
cp -rv fakereg $NAME-$VERSION/
cp -rv defaultconf $NAME-$VERSION/
#cp -rv doc $NAME-$VERSION/

for fn in LICENSE setup.py fakeregks.py fakeregplot.py; do
  cp -v $fn $NAME-$VERSION/
done

tar cvf - $NAME-$VERSION | bzip2 > $NAME-$VERSION.tar.bz2
rm -rf $NAME-$VERSION

echo
echo "Done"
echo

