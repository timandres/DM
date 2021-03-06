goog.provide('sc.data.TurtleSerializer');

goog.require('sc.data.Serializer');
goog.require('sc.data.QuadStore');

sc.data.TurtleSerializer = function(databroker) {
    sc.data.Serializer.call(this, databroker);

    this.compact = true;
    this.indentString = '  ';
};
goog.inherits(sc.data.TurtleSerializer, sc.data.Serializer);

sc.data.TurtleSerializer.prototype.serializableTypes = new goog.structs.Set([
    'text/turtle',
    'text/n3'
]);

sc.data.TurtleSerializer.prototype.serialize = function(quads, opt_format, handler) {
    var format = opt_format || 'text/turtle';

    setTimeout(function() {
        var lines = [];

        lines.push(this.getPrefixesString(this.databroker.namespaces));

        lines.push(this.getTriplesString(quads));

        if (this.compact) {
            var data = lines.join('\n');
        }
        else {
            var data = lines.join('\n\n');
        }

        setTimeout(function() {
            handler(data, null, format);
        }.bind(this), 1);
    }.bind(this), 1);
};

sc.data.TurtleSerializer.prototype.getTriplesString = function(quads) {
    var quadStore = new sc.data.QuadStore(quads);

    var lines = [];

    var subjects = quadStore.subjectsSetMatchingQuery(null, null, null, null);
    goog.structs.forEach(subjects, function(subject) {
        var entry = [this.formatValue(subject)];

        var predicates = quadStore.predicatesSetMatchingQuery(subject, null, null, null);
        var predicateEntries = [];
        goog.structs.forEach(predicates, function(predicate) {
            var objects = quadStore.objectsSetMatchingQuery(subject, predicate, null, null);
            var objectsString;
            if (objects.getCount() == 1) {
                objectsString = ' ' + this.formatValue(objects.getValues()[0]);
            }
            else {
                objectEntries = [];
                goog.structs.forEach(objects, function(object) {
                    objectEntries.push((this.compact ? ' ' : '\n' + this.getIndent(2)) + object);
                }, this);
                objectsString = objectEntries.join(',');
            }

            predicateEntries.push([(this.compact ? ' ' : '\n' + this.getIndent(1)), this.formatValue(predicate), objectsString].join(''));
        }, this);

        lines.push([subject, predicateEntries.join(' ;'), ' .'].join(''));
    }, this);

    if (this.compact) {
        return lines.join('\n');
    }
    else {
        return lines.join('\n\n');
    }
};

sc.data.TurtleSerializer.prototype.getPrefixesString = function(namespaces) {
    var lines = [];

    goog.structs.forEach(namespaces.uriByPrefix, function(uri, prefix) {
        lines.push(['@prefix ', prefix, ': ', sc.data.Term.wrapUri(uri), ' .'].join(''));
    }, this);

    return lines.join('\n');
};

sc.data.TurtleSerializer.prototype.formatValue = function(value) {
    if (sc.data.Term.isWrappedUri(value)) {
        if (value instanceof sc.data.Uri && value.equals('<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>')) {
            return 'a';
        }
        else if (value == '<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>') {
            return 'a';
        }
        else {
            return this.databroker.namespaces.prefix(value);
        }
    }
    else if (sc.data.Term.isLiteral(value)) {
        var lastIndexOfQuote = value.lastIndexOf('"')
        var literalSegment = value.substring(1, lastIndexOfQuote);
        var typeSegment =  lastIndexOfQuote != value.length - 1 ? value.substring(lastIndexOfQuote + 1, value.length) : '';

        if (value.indexOf('\n') != -1) {
            var parts = ['"""', literalSegment, '"""', typeSegment];

            value = parts.join('');
        }
        else {
            var parts = ['"', literalSegment, '"', typeSegment];

            value = parts.join('');
        }

        return value;
    }
    else {
        return value;
    }
};

sc.data.TurtleSerializer.prototype.getIndent = function(level) {
    var arr = [];

    for (var i=0; i<level; i++) {
        arr.push(this.indentString);
    }

    return arr.join('');
};