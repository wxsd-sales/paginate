import hashlib
import hmac

def valid_secret(request, secret_phrase):
    hashed = hmac.new(bytes(secret_phrase, 'latin-1'), request.body, hashlib.sha1)
    validatedSignature = hashed.hexdigest()
    print('compare_secret:validatedSignature:{0}'.format(validatedSignature))
    print('compare_secret:X-Spark-Signature:{0}'.format(request.headers.get('X-Spark-Signature')))
    equal = validatedSignature == request.headers.get('X-Spark-Signature')
    print('compare_secret:Equal? {0}'.format(equal))
    print('compare_secret:secret_phrase.lower()=="none"?:{0}'.format(secret_phrase.lower() == "none"))
    return equal or secret_phrase.lower() == "none"
