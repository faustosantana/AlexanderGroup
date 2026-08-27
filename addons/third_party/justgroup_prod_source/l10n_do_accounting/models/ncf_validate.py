# ncf.py - Validate Dominican Republic NCF (Números de Comprobante Fiscal)

def compact(number):
    """Remove non-digit characters and convert to uppercase."""
    return ''.join(filter(lambda x: x.isalnum(), number)).upper()


_ncf_document_types = {'01', '02', '03', '04', '11', '12', '13', '14', '15', '16', '17'}
_ecf_document_types = {'31', '32', '33', '34', '41', '43', '44', '45', '46', '47'}


def validate(number):
    """Validate the format and structure of an NCF number."""
    number = compact(number)
    
    if len(number) == 13:
        if number[0] != 'E' or not number[1:].isdigit():
            raise ValueError("Invalid e-CF format.")
        if number[1:3] not in _ecf_document_types:
            raise ValueError("Invalid e-CF document type.")
    
    elif len(number) == 11:
        if number[0] != 'B' or not number[1:].isdigit():
            raise ValueError("Invalid NCF format.")
        if number[1:3] not in _ncf_document_types:
            raise ValueError("Invalid NCF document type.")
    
    elif len(number) == 19:
        if number[0] not in 'AP' or not number[1:].isdigit():
            raise ValueError("Invalid 19-digit NCF format.")
        if number[9:11] not in _ncf_document_types:
            raise ValueError("Invalid 19-digit NCF document type.")
    
    else:
        raise ValueError("Invalid NCF length.")
    
    return number


def is_valid(number):
    """Check if the number is a valid NCF."""
    try:
        validate(number)
        return True
    except ValueError:
        return False
