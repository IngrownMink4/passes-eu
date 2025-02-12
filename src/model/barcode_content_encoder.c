#include <stdio.h>
#include <zint.h>
#include <stdlib.h>

const char FOREGROUND = '1';
const char BACKGROUND = '2';
char * last_result = NULL;

enum BarcodeType
{
    AZTEC = 0,
    CODE128,
    PDF417,
    QRCODE
};

char * encode_2d_symbol(struct zint_symbol* symbol, unsigned char * data);
char * encode_barcode(unsigned char * data, unsigned symbology, unsigned * out_width, unsigned * out_height);

char * encode_2d_symbol(struct zint_symbol* symbol, unsigned char * data)
{
    symbol->input_mode = DATA_MODE; // DATA_MODE | UNICODE_MODE
    symbol->output_options |= OUT_BUFFER_INTERMEDIATE;

    ZBarcode_Encode_and_Buffer(symbol, data, 0, 0);

    unsigned amount_of_modules = (symbol->height * symbol->width) + 1;
    unsigned module_size = symbol->bitmap_width / symbol->width;

    char* modules = malloc(amount_of_modules * sizeof(char));

    unsigned bitmap_index = 0;
    unsigned modules_index = 0;
    for (int row = 0; row < symbol->height; row++)
    {
        for (int column = 0; column < symbol->width; column++)
        {
            char module = symbol->bitmap[bitmap_index] == FOREGROUND?
                FOREGROUND : BACKGROUND;

            modules[modules_index] = module;

            bitmap_index += module_size;
            modules_index++;
        }

        bitmap_index += symbol->width * module_size;
    }

    modules[amount_of_modules - 1] = '\0';

    return modules;
}

char * encode_barcode(unsigned char * data,
                      unsigned symbology,
                      unsigned * out_width,
                      unsigned * out_height)
{
    struct zint_symbol* symbol;

    symbol = ZBarcode_Create();

    switch (symbology)
    {
        case AZTEC:
            symbol->symbology = BARCODE_AZTEC;
            break;

        case CODE128:
            symbol->symbology = BARCODE_CODE128;
            break;

        case PDF417:
            symbol->symbology = BARCODE_PDF417;
            break;

        case QRCODE:
            symbol->symbology = BARCODE_QRCODE;
            symbol->option_1 = 1; // Error Correction Level L=1 M=2 Q=3 H=4
            break;
    }

    last_result = encode_2d_symbol(symbol, data);
    *out_width = symbol->width;
    *out_height = symbol->height;

    ZBarcode_Delete(symbol);

    return last_result;
}

void free_last_result()
{
    if (last_result == NULL)
    {
        return;
    }

    free(last_result);
    last_result = NULL;
}
