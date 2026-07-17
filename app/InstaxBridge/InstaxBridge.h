#import <CoreGraphics/CoreGraphics.h>
#import <Foundation/Foundation.h>

NS_ASSUME_NONNULL_BEGIN

@interface IFModeInfo : NSObject

@property(nonatomic, copy, readonly) NSString *name;
@property(nonatomic, readonly) float defaultStrength;
@property(nonatomic, readonly) float defaultGrain;
@property(nonatomic, readonly) float defaultFlash;
@property(nonatomic, readonly) BOOL defaultFrame;

@end

@interface IFProcessingRequest : NSObject

@property(nonatomic, copy) NSString *mode;
@property(nonatomic) float strength;
@property(nonatomic) float grain;
@property(nonatomic) float flash;
@property(nonatomic) BOOL vignette;
@property(nonatomic) BOOL frame;
@property(nonatomic) uint64_t seed;

@end

@interface IFProcessor : NSObject

@property(nonatomic, copy, readonly) NSArray<IFModeInfo *> *availableModes;

- (nullable CGImageRef)processImage:(CGImageRef)image
                            request:(IFProcessingRequest *)request
                              error:(NSError **)error CF_RETURNS_RETAINED;

@end

FOUNDATION_EXPORT NSErrorDomain const IFProcessorErrorDomain;

NS_ASSUME_NONNULL_END
